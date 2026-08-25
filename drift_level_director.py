"""
DriftLevelDirector
==================
Voyager 内嵌的「Drift 关卡 / 世界线 Director」。

关键修正：世界是 Voyager 自己的 Minecraft 世界，Drift 不是独立服务器，
而是 Voyager 进程里的一个子系统，负责：
  1. inject_level(nl)         —— 用 LLM 把自然语言转成「场景叙事 + 任务队列 + 世界补丁(JS)」
  2. propose_next_task(...)    —— 产出当前关卡任务，context 里注入场景叙事
  3. observe_result(info,...) —— 回收 Voyager 的成败，演化世界线；失败太多就改世界（回旋镖）
  4. pending_patches           —— DriftVoyager 主循环通过 env.step 在 *同一个* 世界里执行这些 JS

所有环境修改都发生在 Voyager 连接的那一个 MC 世界里（通过 bot.chat 原生命令），
不依赖任何外部 Drift 后端进程。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Prompt 模板
# ---------------------------------------------------------------------------

INJECT_PROMPT = """你是一个 Minecraft 剧情/关卡设计师，也是 Voyager 这个 embodied agent 的「世界线导演」。
用户用自然语言描述了一个想在 Voyager 的 Minecraft 世界里建立的场景/关卡。
请只输出一段合法 JSON（不要任何解释、不要 markdown 代码块）：
{{
  "scene_narrative": "持续注入给 Voyager 的场景叙事文本（让它相信并理解自己身处该场景，200字以内，中文）",
  "tasks": [
    "关卡任务1（必须是 Voyager 可执行的英文指令，如 Obtain 5 white wool）",
    "任务2", "任务3"
  ],
  "world_patches": [
    "一段可在 Voyager 世界里直接执行的 JS 代码（用 bot.chat('/setblock ...')、bot.chat('/summon ...')、bot.chat('/weather ...') 等原生命令搭建场景；若不需要搭建筑则为空数组"
  ]
}}
要求：
- tasks 由易到难，且都能在 Minecraft 里用 bot 动作完成（采集/合成/放置/对话/移动）。
- world_patches 里的每条都是独立可执行的 JS 字符串，禁止调用未定义的函数。
- 只输出合法 JSON。

自然语言描述：
{nl}"""

ADAPT_PROMPT = """Voyager 在以下关卡任务上反复失败：{task}
当前场景叙事：{scene}
最近事件（task/success）：{log}
你是世界线导演。请通过「改变世界」来帮 Voyager 跨过这个 Gap，而不是只改文字。
请只输出合法 JSON：
{{
  "world_patches": [
    "一段 JS（用 bot.chat('/give @s ...') 给材料 / bot.chat('/setblock ...') 搭脚手架 / bot.chat('/summon ...') 召唤引导NPC），帮助它达成任务"
  ],
  "easier_task": "一个更简单、可达成的替代任务（英文）；若不需要替代就填空字符串"
}}
只输出合法 JSON。"""

NARRATE_PROMPT = """你是 Minecraft 剧情 narrator。Voyager 刚刚完成：{task}
当前世界线最后一段：{scene}
请用一两句话推进剧情，描述这个完成带来的世界变化（中文，60字内）。只返回叙事文本。"""

RESYNTH_PROMPT = """下面是 Voyager 在某一关卡里的世界线演进记录（按时间）：
{history}
请用一段 200 字以内的中文，重新概括 Voyager 当前所处的「场景叙事」，作为接下来注入给它的持续上下文。
只返回叙事文本。"""

# 医院关卡的确定性脚手架（LLM 不产出补丁时的兜底，保证 MVE 可跑）
HOSPITAL_SCAFFOLD_PATCH = """
const p = bot.entity.position;
const ox = Math.floor(p.x), oy = Math.floor(p.y), oz = Math.floor(p.z);
for (let dx=-2; dx<=2; dx++){
  for (let dz=-2; dz<=2; dz++){
    bot.chat(`/setblock ${ox+dx} ${oy-1} ${oz+dz} white_wool`);
  }
}
for (let dx=-2; dx<=2; dx++){
  bot.chat(`/setblock ${ox+dx} ${oy} ${oz-2} white_wool`);
  bot.chat(`/setblock ${ox+dx} ${oy} ${oz+2} white_wool`);
  bot.chat(`/setblock ${ox-2} ${oy} ${oz+dx} white_wool`);
  bot.chat(`/setblock ${ox+2} ${oy} ${oz+dx} white_wool`);
}
bot.chat(`/summon villager ${ox} ${oy+1} ${oz+1} {CustomName:'"Doctor"'}`);
bot.chat('/weather clear');
bot.chat('/time set day');
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found")
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("unbalanced JSON")


class DriftLevelDirector:
    def __init__(
        self,
        llm: Callable[[list[dict], float], str],
        ckpt_dir: str = "ckpt",
        scene_name: str = "main_worldline",
        curriculum=None,
        max_fail_before_adapt: int = 2,
    ):
        self.llm = llm  # llm(messages, temperature) -> str
        self.ckpt_dir = Path(ckpt_dir)
        self.ckpt_dir.mkdir(parents=True, exist_ok=True)
        self.scene_name = scene_name
        self.curriculum = curriculum  # Voyager 的 CurriculumAgent，用于兜底与 qa
        self.max_fail_before_adapt = max_fail_before_adapt

        self.worldline: list[dict] = []     # 世界线快照
        self.scene_narrative: str = ""       # 持续注入给 Voyager 的场景叙事
        self.task_queue: list[dict] = []     # [{task, type, done}]
        self.completed: list[str] = []
        self.failed: list[str] = []
        self.event_log: list[dict] = []
        self.pending_patches: list[str] = []  # 待在 Voyager 世界执行的 JS
        self._fail_streak = 0
        self._load()

    # ---- 持久化 ----------------------------------------------------------
    def _path(self) -> Path:
        return self.ckpt_dir / "drift_worldline.json"

    def save(self) -> None:
        payload = {
            "scene_name": self.scene_name,
            "worldline": self.worldline,
            "scene_narrative": self.scene_narrative,
            "task_queue": self.task_queue,
            "completed": self.completed,
            "failed": self.failed,
            "event_log": self.event_log,
        }
        self._path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _load(self) -> None:
        p = self._path()
        if not p.exists():
            return
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            self.worldline = d.get("worldline", [])
            self.scene_narrative = d.get("scene_narrative", "")
            self.task_queue = d.get("task_queue", [])
            self.completed = d.get("completed", [])
            self.failed = d.get("failed", [])
            self.event_log = d.get("event_log", [])
        except Exception as e:
            print(f"[drift] load worldline failed: {e}")

    # ---- 关卡注入 --------------------------------------------------------
    def inject_level(self, nl_text: str, *, build_scaffold: bool = True, title: str = "") -> dict:
        raw = self.llm(
            [{"role": "user", "content": INJECT_PROMPT.format(nl=nl_text)}], 0.6
        )
        try:
            data = _extract_json(raw)
        except Exception as e:
            print(f"[drift] inject parse failed ({e}); using raw description as scene.")
            data = {"scene_narrative": nl_text, "tasks": [], "world_patches": []}

        self.scene_narrative = data.get("scene_narrative", nl_text) or nl_text
        for t in data.get("tasks", []):
            if t and isinstance(t, str):
                self.task_queue.append({"task": t, "type": "drift", "done": False})

        patches = list(data.get("world_patches", []))
        # 医院关卡的确定性兜底脚手架
        if build_scaffold and not patches and ("医院" in nl_text or "hospital" in nl_text.lower()):
            patches.append(HOSPITAL_SCAFFOLD_PATCH)
        self.pending_patches.extend(patches)

        self.worldline.append(
            {"event": "inject", "narrative": self.scene_narrative, "ts": time.time()}
        )
        self.save()
        return {
            "scene": self.scene_narrative,
            "tasks": [t["task"] for t in self.task_queue],
            "patches": len(self.pending_patches),
        }

    # ---- 任务产出（劫持 curriculum.propose_next_task） ------------------
    def propose_next_task(self, events=None, chest_observation="", max_retries=5):
        # 没注入任何关卡时，交给原始 curriculum（让 Voyager 先学基础技能）
        if not self.task_queue and not self.scene_narrative:
            if self.curriculum is not None:
                return self.curriculum.propose_next_task(
                    events=events, chest_observation=chest_observation, max_retries=max_retries
                )
            return "Mine 1 wood log", "Bootstrap before any Drift level is injected."

        # 队列空但有场景：让 LLM 续写下一阶段任务（世界线演化）
        if not self.task_queue:
            self._extend_tasks(events)

        nxt = next((t for t in self.task_queue if not t["done"]), None)
        if nxt is None:
            return None, self.scene_narrative

        task = nxt["task"]
        context = self.scene_narrative
        if self.curriculum is not None:
            try:
                context += "\n\n" + self.curriculum.get_task_context(task)
            except Exception:
                pass
        return task, context

    def _extend_tasks(self, events) -> None:
        prompt = (
            "当前场景：" + self.scene_narrative +
            "\n已有任务都已完成。请提出接下来 1-3 个 Voyager 可执行的英文任务，"
            "继续推进这个场景（如完善医院、服务更多患者）。只返回 JSON："
            '{"tasks": ["task1", "task2"]}'
        )
        try:
            data = _extract_json(self.llm([{"role": "user", "content": prompt}], 0.5))
            for t in data.get("tasks", []):
                if t and isinstance(t, str):
                    self.task_queue.append({"task": t, "type": "drift", "done": False})
        except Exception as e:
            print(f"[drift] extend tasks failed: {e}")

    # ---- 回收成败（劫持 learn 循环里的 update_exploration_progress 之后） -
    def observe_result(self, info: dict, events=None) -> None:
        task = info.get("task")
        success = bool(info.get("success", False))
        self.event_log.append({"task": task, "success": success, "ts": time.time()})

        if success:
            self._mark_done(task)
            self.completed.append(task)
            self._fail_streak = 0
            beat = self._narrate(task)
            self.worldline.append(
                {"event": "complete", "task": task, "narrative": beat, "ts": time.time()}
            )
            self.scene_narrative = self._resynthesize_scene()
        else:
            self.failed.append(task)
            self._fail_streak += 1
            if self._fail_streak >= self.max_fail_before_adapt:
                patch = self._adapt(task, events)
                if patch:
                    self.pending_patches.append(patch)
                self._fail_streak = 0
        self.save()

    def _mark_done(self, task) -> None:
        for t in self.task_queue:
            if t["task"] == task:
                t["done"] = True

    def _narrate(self, task: str) -> str:
        try:
            return self.llm(
                [{"role": "user", "content": NARRATE_PROMPT.format(task=task, scene=self.scene_narrative)}],
                0.7,
            ).strip()
        except Exception:
            return ""

    def _resynthesize_scene(self) -> str:
        history = "\n".join(
            f"- {w.get('event')}: {w.get('narrative', '')}" for w in self.worldline[-6:]
        )
        try:
            return self.llm(
                [{"role": "user", "content": RESYNTH_PROMPT.format(history=history)}], 0.4
            ).strip()
        except Exception:
            return self.scene_narrative

    def _adapt(self, task: str, events) -> str | None:
        log = json.dumps(self.event_log[-5:], ensure_ascii=False)
        raw = self.llm(
            [{"role": "user", "content": ADAPT_PROMPT.format(task=task, scene=self.scene_narrative, log=log)}],
            0.4,
        )
        try:
            data = _extract_json(raw)
        except Exception:
            return None
        for p in data.get("world_patches", []):
            if p:
                self.pending_patches.append(p)
        easier = data.get("easier_task")
        if easier and isinstance(easier, str) and easier.strip():
            self.task_queue.insert(0, {"task": easier.strip(), "type": "drift_adapt", "done": False})
        return data.get("world_patches", [""])[0] or None

    # ---- 观测 ------------------------------------------------------------
    def timeline(self) -> list[dict]:
        """给外部观测面板用：世界线 + 任务完成情况。"""
        return {
            "scene": self.scene_narrative,
            "worldline": self.worldline,
            "completed": self.completed,
            "failed": self.failed,
            "pending_patches": len(self.pending_patches),
            "remaining_tasks": [t["task"] for t in self.task_queue if not t["done"]],
        }
