"""
DriftLevelDirector —— Drift 作为 Voyager 进程内的「关卡 Director」。

职责：
  1. inject_level():   把自然语言关卡文本注入 Drift 后端(真实 LLM 生成场景/世界补丁)
  2. propose_next_task(): 把 Drift 当前世界线/场景叙事 + 世界补丁 翻译成 Voyager 的
                         (task, context)。context 注入 ActionAgent 的 `Context:` 字段
                         (即「骗 Voyager 进入场景」的引导机制)。并用一次 LLM 调用把
                         关卡拆成若干可执行子任务。
  3. observe_result():  把 Voyager 的成败回灌 Drift ——
                         - /story/advance 携带 action=结果 -> 推进剧情、演化世界补丁
                         - /add          写入世界线 ledger(可观察的演化记录)

这就是心悦说的「回旋镖」闭环：Voyager 行为 -> Drift 改世界 -> 再塑造下一轮 Voyager。
"""

import os
import json
import time
import requests


class DriftLevelDirector:
    def __init__(
        self,
        drift_base="http://127.0.0.1:8011",
        player_id="bot",
        level_text="",
        level_title="小镇医院",
        log=print,
    ):
        self.base = drift_base.rstrip("/")
        self.player = player_id
        self.level_text = level_text
        self.level_title = level_title
        self.log = log

        # 每次运行用唯一 level_id，避免 Drift 报 "already exists"
        self.level_id = f"flagship_hospital_{int(time.time())}"
        self.plan = []           # 由 LLM 拆解出的子任务列表(仅兜底用)
        self.idx = 0             # 兜底计划游标
        self.task_no = 0         # 已派发的任务计数(用于展示)
        self.narrative = ""      # 当前 Drift 场景叙事(来自 advance 的 node)
        self.last_patch = {}     # 最近一次 advance 返回的 world_patch
        self.world_line = []     # 结束时拉取的世界线 ledger

    # ------------------------------------------------------------------
    # Director 自带 LLM(DeepSeek) —— 仅用于「把关卡拆成子任务」
    # (Drift 的叙事/世界补丁由 Drift 后端自己的 LLM 生成)
    # ------------------------------------------------------------------
    def _chat(self, system, user, temperature=0.0):
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        base = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        if not key:
            raise RuntimeError("DEEPSEEK_API_KEY 未设置")
        r = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _extract_json(text):
        for a, b in (("{", "}"), ("[", "]")):
            try:
                s = text.index(a)
                e = text.rindex(b)
                return json.loads(text[s : e + 1])
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # Drift 后端调用
    # ------------------------------------------------------------------
    def inject_level(self):
        """把自然语言关卡注入 Drift，并拆解成本地执行计划。"""
        body = {
            "level_id": self.level_id,
            "title": self.level_title,
            "text": self.level_text,
            "player_id": self.player,
        }
        r = requests.post(f"{self.base}/story/inject", json=body, timeout=180)
        self.log(f"[Drift] inject {self.level_id} -> {r.status_code}")
        try:
            self.log(f"[Drift] inject body(head): {r.text[:240]}")
        except Exception:
            pass

        self.plan = self._decompose()
        # 第一次 advance：拿到开场叙事 + 初始世界补丁
        self._advance(None)
        try:
            return r.json()
        except Exception:
            return {"status_code": r.status_code}

    def _decompose(self):
        """把关卡先粗拆成若干候选子任务，仅作为 LLM 动态出题失败时的兜底(不要强来)。"""
        sys_msg = (
            "你是 DriftSystem 的关卡拆解器。把一个用自然语言注入的 Minecraft 关卡，"
            "拆解成若干 Voyager(一个能执行 JS 代码的 Minecraft bot)可以逐步完成的子任务。\n"
            "原则(不要强来)：\n"
            "1. 一次只推进一小步；若任务需要 bot 手上没有的材料，可用 "
            "bot.chat('/give @s minecraft:<物品> <数量>') 获取，也可先去采集；\n"
            "2. 尽量用 bot.chat('/指令') 或标准动作完成，最后用 bot.chat('...完成') 汇报；\n"
            "3. 任务应当循序渐进，让 bot 逐步学会，而不是硬塞一整座建筑。\n"
            "只返回 JSON 数组，例如 [\"任务1\",\"任务2\",\"任务3\"]。"
        )
        usr = f"关卡描述：{self.level_text}"
        try:
            out = self._chat(sys_msg, usr)
            data = self._extract_json(out)
            if isinstance(data, list) and data:
                return [str(x).strip() for x in data if str(x).strip()][:6]
        except Exception as e:
            self.log(f"[Drift] decompose failed: {e}")
        # 兜底计划(顺序由易到难，自然递进)
        return [
            "先去获取一些白色羊毛：用 bot.chat('/give @s minecraft:white_wool 32') 取得材料，"
            "并 bot.chat('已取得白色羊毛') 汇报。",
            "在脚下用 bot.chat('/setblock x y z minecraft:white_concrete') 之类指令，"
            "搭建一间小小的白色诊室(用 bot.position 计算坐标，留一个门洞)，完成后 bot.chat('诊室已搭建')。",
            "召唤一位医生 NPC 并对话：bot.chat('/summon villager ~ ~1 ~ "
            "{CustomName:\"\\\\\\\"医生\\\\\\\",CustomNameVisible:true,profession:cleric}')，"
            "然后 bot.chat('医生，有患者需要救治') 完成接诊，bot.chat('接诊完成')。",
        ]

    def _propose_next_task_text(self, last_info):
        """
        基于 Drift 当前世界叙事 + 上一步结果，由 LLM 生成『下一个』单一任务(真实回旋镖)。
        返回任务字符串，或哨兵 '__DONE__' 表示关卡已自然学会/达成，无需继续强推。
        """
        last = ""
        if last_info is not None:
            last = (
                f"上一步任务：{last_info.get('task','')}\n"
                f"上一步是否成功：{last_info.get('success')}\n"
            )
        sys_msg = (
            "你是 DriftSystem 的关卡推进器，负责给 Minecraft bot(Voyager)派发【下一个】可执行任务。\n"
            "Voyager 是能执行 JS 的 bot，只能做 Minecraft 里真实存在的动作，例如：\n"
            "  - bot.chat('/give @s minecraft:<物品> <数量>')            // 获取材料\n"
            "  - bot.chat('/setblock <x> <y> <z> minecraft:<方块>')      // 放置/搭建方块\n"
            "  - bot.chat('/summon villager ~ ~1 ~ {CustomName:\"\\\\\\\"医生\\\\\\\",CustomNameVisible:true,profession:cleric}')  // 召唤医生NPC\n"
            "  - bot.chat('/fill ...')、bot.chat('/clear @s') 等标准指令，以及用 bot.position 计算坐标后汇报\n"
            "硬性要求(必须可执行，禁止虚构剧情)：\n"
            "1. 每次只给【一个】任务，且必须是上面这类 bot 能在数十秒内真实完成的动作；\n"
            "2. 绝对禁止派发『去找铁匠/去村庄交易/去山洞挖矿/找回某物』等 bot 无法执行的剧情任务；\n"
            "3. 围绕『医院』目标循序渐进：先取得材料(白色羊毛/混凝土)→ 搭建诊室 → 召唤医生NPC → 汇报救治；\n"
            "4. 若上一步失败，就给一个更简单、确定能成的 bot.chat 指令(例如改为 /give 直接获取材料或 /setblock 搭一块)，不要重复高难动作；\n"
            "5. 当诊室已搭好、医生NPC已召唤、并能 bot.chat('医院已就绪') 汇报时，只回复 '__DONE__'；\n"
            "6. 否则只回复一句【具体 bot 动作】描述(中文，可含指令示例)，不要解释、不要加前缀。"
        )
        usr = (
            f"【关卡目标】{self.level_text}\n"
            f"【当前世界叙事 / 场景】{self.narrative}\n"
            f"【当前世界补丁】{json.dumps(self.last_patch, ensure_ascii=False)[:600]}\n"
            f"{last}\n"
            "请给出下一个任务，或 __DONE__。"
        )
        try:
            out = self._chat(sys_msg, usr, temperature=0.2).strip()
            if "__DONE__" in out:
                return "__DONE__"
            for p in ("> ", "任务：", "下一步：", "任务:", "下一步:", '"', "'"):
                if out.startswith(p):
                    out = out[len(p):].strip()
            if out:
                return out
        except Exception as e:
            self.log(f"[Drift] next-task gen failed: {e}")
        # 兜底：从预拆解计划里取下一个
        if self.plan and self.idx < len(self.plan):
            t = self.plan[self.idx]
            self.idx += 1
            return t
        return "__DONE__"

    def _advance(self, info):
        """推进 Drift 剧情。携带 Voyager 上一步结果作为 action -> 演化世界补丁。"""
        action = {}
        if info is not None:
            action = {
                "type": "task_result",
                "success": bool(info.get("success")),
                "task": str(info.get("task", "")),
            }
        try:
            r = requests.post(
                f"{self.base}/story/advance/{self.player}",
                json={"world_state": {}, "action": action},
                timeout=180,
            )
            j = r.json()
            self.last_patch = j.get("world_patch") or {}
            node = j.get("node")
            if isinstance(node, dict):
                # 取可读字段作为叙事
                self.narrative = json.dumps(node, ensure_ascii=False)[:800]
            elif isinstance(node, str):
                self.narrative = node[:800]
            else:
                self.narrative = ""
            self.log(
                f"[Drift] advance -> patch_keys={list((self.last_patch or {}).keys())} "
                f"node_keys={list(node.keys()) if isinstance(node, dict) else type(node).__name__}"
            )
        except Exception as e:
            self.log(f"[Drift] advance error: {e}")

    def propose_next_task(self, last_info=None):
        """
        返回 (task, context) 或 None(关卡已自然学会/达成)。
        - 用上一步结果推进 Drift 世界线(回旋镖)
        - 由 Drift 当前叙事 + 上一步成败，动态生成【下一个】单一任务(不预排固定计划、不强行推进)
        - context 把 Drift 场景叙事 + 世界补丁 注入 Voyager 的 Context 字段
        """
        if last_info is not None:
            self._advance(last_info)
            # 写入世界线 ledger(可观察演化记录)
            try:
                requests.post(
                    f"{self.base}/add",
                    json={"content": f"task={last_info.get('task')} | success={last_info.get('success')}"},
                    timeout=30,
                )
            except Exception:
                pass

        task = self._propose_next_task_text(last_info)
        if task == "__DONE__":
            self.log("[Drift] 关卡已自然学会/达成，停止推进。")
            return None

        self.task_no += 1
        context = self._build_context()
        return task, context

    def _build_context(self):
        return (
            f"【Drift 用自然语言注入的关卡】{self.level_text}\n"
            f"【当前世界线 / 场景叙事】{self.narrative}\n"
            f"【Drift 生成的世界补丁(应出现在世界中的结构与NPC)】"
            f"{json.dumps(self.last_patch, ensure_ascii=False)[:1000]}\n"
            "你正处于 Drift 用自然语言注入的「医院」关卡中。上方世界补丁描述了应被建造/召唤的内容。"
            "请尽量按关卡推进：使用 bot.chat('/指令') 或标准动作完成任务，并在完成时通过 bot.chat 汇报进度。"
        )

    def finish(self):
        """拉取并保存世界线 ledger(供观察演化)。"""
        try:
            r = requests.get(f"{self.base}/state", timeout=30)
            self.world_line = r.json()
            self.log(f"[Drift] world line: {json.dumps(self.world_line, ensure_ascii=False)[:600]}")
        except Exception as e:
            self.log(f"[Drift] state error: {e}")
        return self.world_line
