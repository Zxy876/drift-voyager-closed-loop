# Drift × Voyager 闭环：自然语言注入关卡，让 Voyager 学习并观察演化

> **一句话**：把 [DriftSystem](https://github.com/) 当作「导演」子系统嵌进 [Voyager](https://github.com/MineDojo/Voyager)，
> 用自然语言往 Voyager 的 Minecraft 世界里注入关卡（例如「建一个小镇医院」），
> Voyager 作为主智能体去执行、学习技能，Drift 根据执行结果推进世界叙事——形成可观察的「回旋镖」演化循环。

---

## 背景与目标

用户在本地（macOS）跑 Voyager + MineDojo，希望验证一个想法：

- **Voyager = 主智能体**：连上 Minecraft，执行动作、学技能、长上下文记忆。
- **DriftSystem = 导演子系统**：用自然语言生成关卡与世界叙事，根据 Voyager 的行为动态调整世界线。
- **回旋镖循环（boomerang）**：Voyager 行为 → Drift 调整世界叙事/补丁 → 重塑下一轮 Voyager 的任务。

**验收标准**：在 Voyager 世界里可以**自然语言注入关卡**（如医院），让 Voyager **学习**，
并且我们可以**观察状态和迭代**（医院演化）。

---

## 架构

```
自然语言关卡("建小镇医院")
        │
        ▼
┌─────────────────┐   注入关卡 / 推进世界线    ┌──────────────────────┐
│  DriftSystem     │ ───────────────────────▶ │  DriftLevelDirector   │
│  (FastAPI :8011) │ ◀─────────────────────── │  (drift_director.py)  │
└─────────────────┘   世界线 ledger / state   └──────────────────────┘
                                                        │ propose_next_task()
                                                        ▼
                                         ┌──────────────────────────┐
                                         │  DriftVoyager(Voyager)    │
                                         │  (voyager_drift.py)       │
                                         │  learn(): 顺序执行子任务   │
                                         └──────────────────────────┘
                                                        │ step() → bot.chat(...)
                                                        ▼
                                         ┌──────────────────────────┐
                                         │  Mineflayer 桥 (:3000)     │
                                         │  (Voyager-main/env/...)    │
                                         └──────────────────────────┘
                                                        │
                                                        ▼
                                                Minecraft 服务器 (:25565)
```

- **LLM 路由**：chat / 任务生成 → DeepSeek(`deepseek-chat`)；embeddings → 智谱(`embedding-3`)。
- **世界线可观测**：`GET http://127.0.0.1:8011/state` 返回任务 success/false 树。
- **技能可观测**：`ckpt/skill/skills.json` 记录 Voyager 学到的技能。

---

## 关键坑与修复（本仓库的核心价值）

run5–run11 长期卡死在 `list index out of range`，最终定位到的根因链：

1. `voyager/agents/action.py` 的 `process_ai_message()` 用
   `babel = require("@babel/core")` 在 Python 侧解析 LLM 返回的 JavaScript；
2. **整个 Voyager 仓库没有安装 `@babel/core`** → `require` 立即抛异常；
3. `process_ai_message` 重试 3 次后返回**字符串**（解析失败信息）；
4. `voyager.py` 的 `step()` 判断该返回值为字符串 → 调用
   `self.recorder.record([], self.task)`，**传入空列表**；
5. `voyager/utils/record_utils.py` 的 `record()` 执行 `events[0][1]["status"]...`
   → **IndexError** → 整个 `rollout` 崩掉，循环停滞。

**修复**（最小改动，已在 fork 中落地）：
- `action.py`：删除 babel 依赖，改用**纯 Python 正则**提取 ```` ```javascript ```` 块里的
  `async function NAME(bot){...}`，生成与原始完全相同的 `{program_code, program_name, exec_code}`。
- `record_utils.py`：`record()` 对空 `events` 加保护，任何解析失败都不会再拖垮整个学习循环。

> 仓库根目录的 `drift_voyager_run_report.md` 有完整记录：环境真相、所有改动清单、复现命令、残余风险。

---

## 目录结构

| 文件 | 作用 |
|---|---|
| `drift_director.py` | `DriftLevelDirector`：推进 Drift、写世界线 ledger、生成「单步可执行 bot 动作」任务 |
| `voyager_drift.py` | `DriftVoyager(Voyager)` 子类：`learn()` 接管为「Drift 驱动 + 顺序执行 + 直到学会」；`rollout()` 含重试自愈 |
| `run_drift_voyager.py` | 入口：路由 LLM、拉起 Drift 后端、注入「建小镇医院」关卡、`player_id="bot"` |
| `drift_level_director.py` | 早期版本导演（保留参考） |
| `run_hospital_demo.py` | 医院关卡演示脚本（参考） |
| `drift_primitives.js` | 注入 Mineflayer 的控制原语 |
| `probe_*.py` | LLM / 智谱 embedding 连通性探针（调试用） |
| `drift_voyager_integration.md` | 集成说明（设计文档） |
| `drift_voyager_run_report.md` | **运行报告**：根因、改动、复现、风险 |
| `.env.example` | 环境变量示例（**不含真实密钥**） |
| `ckpt/` | Voyager 运行产物：学到的技能(`skill/`)、课程(`curriculum/`)、动作记录(`action/`)、事件(`events/`) |

---

## 快速复现

```bash
# 1) 起 Minecraft 服务器（Paper 1.20.1, :25565，bot 设为 op4，online-mode=false）
#    并起 DriftSystem 后端（:8011，环境变量 DRIFT_USE_PAYLOAD_V2=true）

# 2) 准备环境变量
export DEEPSEEK_API_KEY=...      # 必须
export DEEPSEEK_API_BASE=...     # 必须
export ZHIPU_API_KEY=...         # 必须（embeddings）

# 3) 启动闭环（后台）
cd outputs
export PATH=/Users/zxydediannao/.workbuddy/binaries/node/versions/22.22.2/bin:$PATH
export PYTHONUNBUFFERED=1
/Users/zxydediannao/.workbuddy/binaries/python/envs/voyager/bin/python \
    run_drift_voyager.py > /tmp/voyager_drift_run.log 2>&1

# 4) 观察
tail -f /tmp/voyager_drift_run.log
curl -s http://127.0.0.1:8011/state | python3 -m json.tool   # 世界线树
cat ckpt/skill/skills.json                                   # 已学技能
```

---

## 当前成果（run12 实测）

| 指标 | 结果 |
|---|---|
| 崩溃（IndexError） | 0 |
| 完成任务 | 3 |
| 学到的技能 | `giveWhiteWool`、`giveWhiteConcrete` |
| Drift 子任务涌现 | 5（全部由世界叙事驱动） |
| 回旋镖推进 | 5 次，世界线树实时可见 |
| 失败任务 | 1（远处 setblock 白床）优雅跳过，未崩 |

验收标准达成：✅ 自然语言注入关卡 ✅ Voyager 学习（技能入库）✅ 状态与迭代可观察。

---

## 残余限制

1. **关卡任务偏「指令型」**：当前 Drift 生成的子任务多为 `bot.chat('/give ...')` / `/setblock`；
   `world_patch` 目前仅作叙事上下文，未在方块层实例化结构/NPC。「医院真的建出来」需扩展控制原语
   把 `world_patch.mc` 落成方块/实体。
2. **跨维度 / 远坐标任务会失败**：如 `(120,65,80)` 放床，bot 在出生点且目标未加载 → Critic 判失败 → 已优雅跳过。
3. **`@babel` 缺失是框架级坑**：本次用纯 Python 正则绕过；若未来需要 babel 校验/转译，应在对应 node 环境
   `npm i @babel/core @babel/generator`。

---

## 许可证

Voyager / MineDojo 与 DriftSystem 各自沿用其上游许可证；本仓库的集成脚本与文档以 MIT 授权。
