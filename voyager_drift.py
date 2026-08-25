"""
DriftVoyager —— Voyager 主类 + 内嵌 DriftLevelDirector。

世界始终是 Voyager 连接的那一个 MC 世界(25565 上的 DriftSystem Paper 服务器)。
Drift 不是外部服务器，而是进程内的「关卡 Director」：
  - learn() 不再用 curriculum_agent.propose_next_task()，改为 drift.propose_next_task()
  - 每个 rollout 的 (task, context) 中，context 携带 Drift 场景叙事 + 世界补丁，
    注入 ActionAgent 的 `Context:` 字段(即「引导 Voyager 进入场景」)
  - 每个 rollout 的成败(info)回灌 Drift -> 演化世界线(回旋镖闭环)

只改了 learn() 一处接入点，其余(env / action agent / critic / skill manager)完全复用。

额外的健壮性补丁：
  - 用 safe_step 包裹 env.step，确保它【永远不返回空列表】(空列表会让 Voyager 内部
    events[-1] 触发 IndexError)。空时重试，仍为空则合成一条最小合法观测兜底。
  - 所有 except 打印完整 traceback，便于定位。
"""

import time
import traceback

from voyager.voyager import Voyager


# 兜底合成的最小合法观测：满足 critic / action / curriculum 里所有
# events[-1][1]["..."] 的取值，避免任何下游 events[-1] 崩溃。
_FALLBACK_EVENT = [
    [
        "observe",
        {
            "voxels": [],
            "status": {
                "biome": "plains",
                "timeOfDay": "day",
                "health": 20.0,
                "food": 20,
                "saturation": 5,
                "position": {"x": 0, "y": 64, "z": 0},
                "velocity": {"x": 0, "y": 0, "z": 0},
                "yaw": 0,
                "pitch": 0,
                "onGround": True,
                "equipment": [None, None, None, None, None, None],
                "name": "bot",
                "isInWater": False,
                "isInLava": False,
                "isCollidedHorizontally": False,
                "isCollidedVertically": False,
                "entities": {},
                "inventoryUsed": 0,
                "elapsedTime": 0,
            },
            "inventory": {},
            "nearbyChests": {},
            "blockRecords": [],
            "onChat": [],
            "onError": [],
            "onSave": [],
        },
    ]
]


class DriftVoyager(Voyager):
    def __init__(self, *args, drift=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.drift = drift
        self._wrap_env_step()

    # ------------------------------------------------------------------
    # env.step 兜底：永不返回空列表
    # ------------------------------------------------------------------
    def _wrap_env_step(self):
        orig = self.env.step

        def safe_step(code="", programs=""):
            last_err = None
            for attempt in range(4):
                try:
                    data = orig(code, programs)
                except Exception as e:
                    last_err = e
                    print(f"[Drift][safe_step] env.step 异常(重试 {attempt+1}): {e}")
                    traceback.print_exc()
                    time.sleep(2)
                    continue
                if isinstance(data, list) and len(data) > 0:
                    return data
                # 返回了空列表/非列表 -> 强制重新观察并重试
                print(f"[Drift][safe_step] env.step 返回空(重试 {attempt+1})：{type(data)}")
                time.sleep(2)
            if last_err is not None:
                print(f"[Drift][safe_step] 最终仍异常，使用兜底观测：{last_err}")
            else:
                print("[Drift][safe_step] 最终仍空，使用兜底观测")
            return _FALLBACK_EVENT

        self.env.step = safe_step

    # ------------------------------------------------------------------
    # rollout 包一层：环境抖动的兜底
    # ------------------------------------------------------------------
    def rollout(self, *args, reset_env=True, **kwargs):
        try:
            return super().rollout(*args, reset_env=reset_env, **kwargs)
        except (IndexError, TypeError, KeyError, ValueError) as e:
            print(f"[Drift] rollout 重试(环境抖动): {e}")
            traceback.print_exc()
            for _ in range(8):
                try:
                    self.last_events = self.env.reset(
                        options={"mode": "soft", "wait_ticks": self.env_wait_ticks}
                    )
                    self.last_events = self.env.step("")
                except Exception:
                    self.last_events = []
                if self.last_events:
                    break
                time.sleep(3)
            return super().rollout(*args, reset_env=reset_env, **kwargs)

    def learn(self, reset_env=True):
        if self.drift is None:
            return super().learn(reset_env=reset_env)

        print("\n========== DriftLevelDirector: 注入自然语言关卡 ==========")
        self.drift.inject_level()

        # 初次软重置：本服上硬重置的 /kill @s 会把 bot 直接踢下线导致连接中断，
        # 故改用 soft 模式(不清背包也不杀 bot)，随后手动 /clear 清空背包。
        self.env.reset(
            options={"mode": "soft", "wait_ticks": self.env_wait_ticks}
        )
        try:
            self.env.step("bot.chat('/clear @s')")
        except Exception:
            pass
        self.resume = True
        try:
            self.last_events = self.env.step("")
        except Exception:
            self.last_events = []

        last_info = None
        safety = 0
        # 不强行限制步数：让 Drift 在关卡自然学会(__DONE__)时才停止。
        # safety 只是防止意外死循环的兜底。
        while True:
            safety += 1
            if safety > 25:
                print("[Drift] safety break (达到兜底上限)")
                break

            proposal = self.drift.propose_next_task(last_info)
            if proposal is None:
                print("\n========== 关卡子任务执行完毕 ==========")
                break

            task, context = proposal
            print(f"\n========== Drift 子任务 #{self.drift.task_no} ==========\n{task}\n")

            try:
                messages, reward, done, info = self.rollout(
                    task=task, context=context, reset_env=reset_env
                )
            except Exception as e:
                time.sleep(3)
                info = {"task": task, "success": False}
                # 干净软重置(不依赖 last_events 结构, 避免中途崩溃后索引越界)
                try:
                    self.last_events = self.env.reset(
                        options={"mode": "soft", "wait_ticks": self.env_wait_ticks}
                    )
                    self.last_events = self.env.step("")
                except Exception:
                    pass
                print(f"[Drift] rollout error: {e}")
                traceback.print_exc()

            if info.get("success"):
                try:
                    self.skill_manager.add_new_skill(info)
                except Exception:
                    pass

            # 维持 completed/failed 列表(供报告)
            self.curriculum_agent.update_exploration_progress(info)
            last_info = info

        world_line = self.drift.finish()
        return {
            "completed_tasks": self.curriculum_agent.completed_tasks,
            "failed_tasks": self.curriculum_agent.failed_tasks,
            "skills": self.skill_manager.skills,
            "world_line": world_line,
        }
