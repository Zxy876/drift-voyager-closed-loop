# Voyager + Drift：在 Voyager 自己的世界里自然语言建关卡、学习、观察演化

> 修正版：世界是 **Voyager 自己的 Minecraft 世界**，Drift 的「LLM 关卡系统」作为
> **Voyager 进程内的一个 Director 子系统**嵌进去，不是让 Voyager 去连一个外部 Drift 服务器。

## 1. 核心修正（相对上一版）

| 上一版（已废弃） | 本版（正确） |
|---|---|
| Voyager 作为 bot 加入 Drift 的 Paper 服务器 | 世界就是 Voyager 连接的那个 MC 世界 |
| 外部 FastAPI Bridge + Drift 后端 HTTP | DriftLevelDirector 是 Voyager 进程内模块，无外部依赖 |
| 关卡由 Drift 后端生成、经 Bridge 翻译 | 关卡由 Director 用同一个 LLM 直接生成，`context` 注入 Voyager |
| 世界补丁走 Drift 插件协议 | 世界补丁经 `env.step` 在 **Voyager 同一个世界**里用原生命令落地 |

一句话：**Drift = Voyager 的「世界线导演」**，负责出剧情/任务、把场景叙事塞进 Voyager 的
`context`、把成败回收后改世界；Voyager 始终是那个在世界里行动的 agent。

## 2. 系统结构（同一世界，Drift 嵌入 Voyager）

```
                        自然语言注入（"建一个医院"）
                                  │
                                  ▼
                    ┌──────────────────────────────┐
                    │     DriftLevelDirector        │  ← Voyager 进程内
                    │  - scene_narrative (世界线)    │
                    │  - task_queue   (关卡任务)     │
                    │  - pending_patches (JS补丁)    │
                    │  - worldline / event_log      │
                    └───────┬───────────────┬───────┘
            propose_next_task│              │ observe_result(info)
                            ▼              ▲
              task + context(场景叙事)   │  success / failure
                            │              │
                            ▼              │
        ┌──────────────────────────┐      │
        │   Voyager (ActionAgent)  │──────┘  ← 回旋镖闭环
        │   学习技能 / 执行代码     │
        └───────────┬──────────────┘
                    │ env.step(code)
                    ▼
        ┌──────────────────────────┐
        │  Voyager 的 MC 世界       │  ← 同一个世界
        │  (bot 在线，方块/NPC/天气) │
        └──────────────────────────┘
              ▲                  │
    Drift 的世界补丁             │ Voyager 的行为改变世界
    (env.step JS) ──────────────┘ （放置方块、与医生对话…）
```

## 3. 代码级接入点（来自真实代码）

| Voyager 代码 | 原行为 | Drift 接管方式 |
|---|---|---|
| `Voyager.learn()` 中 `curriculum_agent.propose_next_task(...)` | 自动课程生成任务 | 改为 `drift.propose_next_task(...)`，由 Director 产出关卡任务；未注入关卡时内部回退到原 curriculum |
| `Voyager.reset/step` 的 `context` 字段 | QA 得到的“怎么做” | 被替换为 `scene_narrative + qa`，让 bot 相信并理解身处该场景 |
| `Voyager.step()` 返回的 `info{success, task, conversations}` | 仅用于记 ckpt | 额外喂给 `drift.observe_result(...)` 演化世界线 |
| `Voyager.env.step(code)` | 执行 bot 代码 | 也用于执行 Director 的 `pending_patches`（搭建筑/召唤NPC/天气） |

`context` 在 `action_template.txt` 里是独立的 `Context: ...` 字段（`action.py` 第 189-192 行），
正是放「场景叙事 / 世界线」的位置——这保证了“骗 Voyager 进入场景”的引导机制成立。

## 4. 关卡生命周期（闭环）

1. **注入**：`voyager.inject_level("建一个医院…")` → LLM 生成
   `{scene_narrative, tasks[], world_patches[]}`。
2. **落世界**：`learn()` 循环顶部把 `world_patches`（JS，用 `/setblock /summon /weather`）
   经 `env.step` 在 Voyager 世界里执行 → 诊所、医生 NPC、晴朗天气出现。
3. **学习**：Director 产出任务（如 `Obtain 5 white wool`、`Talk to Doctor`），`context` 携带场景叙事，
   Voyager 的 ActionAgent 据此写代码、学技能。
4. **回灌**：每轮 `rollout` 后 `drift.observe_result(info)` 回收成败：
   - 成功 → 世界线追加“完成”节点，重概括场景叙事（演化）。
   - 反复失败 → **Director 改世界**（给材料 / 搭脚手架 / 召唤引导 NPC）或把任务降级，
     这就是聊天里说的「回旋镖」：Voyager 的行为改变环境，环境再塑造下一轮 Voyager。

## 5. 最小可跑通实验（MVE）

**前提**：一个 Minecraft 服务器在 `localhost:25565` 跑着，Voyager 能连上，且 bot 被设为 op
（`/setblock`、`/summon`、`/give` 需要权限）。

1. 配置 `.env`（见 `.env.example`）：填 `ZHIPU_API_KEY`，设 `VOYAGER_ROOT`、`MC_PORT`。
2. 运行：
   ```bash
   cd /Users/zxydediannao/WorkBuddy/2026-08-25-16-13-39/outputs
   python run_drift_voyager.py --level "建一个医院：一间诊室，一位医生NPC，患者缺少白色羊毛绷带。让 Voyager 学习搭建诊所、获取羊毛、与医生对话完成救治。"
   ```
3. 观察：
   - 控制台应出现 `[drift] applied world patch` → 诊所与 Doctor NPC 在 Voyager 世界里出现。
   - 任务队列被逐个执行；成功/失败写入 `ckpt/drift_worldline.json`。
   - 运行结束打印 `drift worldline timeline`，可看到场景叙事随完成而演化。

**验证指标**：
- [ ] Voyager 加入自己的 MC 世界（非外部 Drift 服）。
- [ ] 自然语言注入后，诊所/医生/天气在 *同一个* 世界里出现。
- [ ] Voyager 至少完成一个 Director 派生任务（并因此学到技能）。
- [ ] 失败任务触发 Director 改世界（如给材料 / 搭脚手架）或任务降级。
- [ ] 同关卡两轮后，场景叙事或任务发生变化（演化可见）。

## 6. Voyager 侧需要的最小扩展

- **drift_primitives.js**：`driftTalkToNpc / driftWaitForChat / driftSummonNpc / driftBuildStructure /
  driftGive / driftSetWeather`，由 `enable_drift_primitives()` 注入 action agent 上下文与执行环境，
  使 Voyager 能在任务里学习“与医生对话 / 召唤 NPC / 搭建筑”。
- **critic prompt**（可选增强）：在 `voyager/prompts/critic.txt` 追加对“对话/到达/放置”类任务的判定说明，
  让 Critic 能依据聊天日志、位置、附近方块判断成功。
- **action template**（可选增强）：在 `action_template.txt` 的 programs 说明里提及 `drift*` 原语。

## 7. 风险与兜底

| 风险 | 兜底 |
|---|---|
| bot 无权限执行 `/setblock` 等 | 把 bot 设为 op；或改用 `bot.placeBlock` 等 API（需在原语里实现） |
| Voyager mineflayer 与服务器版本不兼容 | 确认服务器版本与 mineflayer 匹配（Voyager 自带 4.8.1，对应 1.19.x；若服务器是 1.20.1 需升级 mineflayer/minecraft-data） |
| LLM 生成的 JSON/补丁不可靠 | `_extract_json` 容错；医院关卡有确定性 `HOSPITAL_SCAFFOLD_PATCH` 兜底 |
| 对话类任务反复失败 | `driftTalkToNpc` + `driftWaitForChat`；Director `_adapt` 会改世界或降级任务 |
| 费用不可控 | 每个 task 最多 4 次 retry；`max_iterations` 上限；失败自动归档 |

## 8. 文件清单（本目录 outputs/）

| 文件 | 作用 |
|---|---|
| `drift_level_director.py` | 进程内 Drift Director：注入关卡、产出任务、回收成败、改世界 |
| `voyager_drift.py` | `DriftVoyager(Voyager)` 子类 + `ZhipuLLM` + 工厂 + 原语注入 |
| `run_drift_voyager.py` | 入口：自然语言注入关卡 → `learn()` 闭环 |
| `drift_primitives.js` | Voyager 可学习的 Drift 控制原语 |
| `drift_voyager_integration.md` | 本方案 |
| `.env.example` | 环境变量模板 |

> 旧版 `drift_voyager_bridge.py`（外部 FastAPI）已被本方案取代，不再使用。
