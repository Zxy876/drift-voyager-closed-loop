# Drift × Voyager 闭环运行报告（自然语言注入"医院"关卡）

> 目标：在 Voyager 的 Minecraft 世界里，用 DriftSystem 以自然语言注入关卡（如"小镇医院"），
> 让 Voyager 作为主智能体学习/演化，人类可观察其状态与迭代（医院演化）。
> 验收标准：**自然语言注入关卡 → Voyager 学习（技能入库）→ 状态与迭代可观察**。

---

## 一、最终结论

✅ **闭环已跑通**。run12（2026-08-25 18:5x 起）实测结果：

| 指标 | run12 实测 |
|---|---|
| rollout 崩溃（IndexError） | **0 次**（历史 run5–run10 长期卡死在此） |
| 完成任务 | 3 个（give white_wool / give white_concrete / 再次 give white_wool） |
| Voyager 学到并落盘技能 | `giveWhiteWool`、`giveWhiteConcrete` 已写入 `ckpt/skill/skills.json` |
| Drift 子任务涌现 | 5 个，全部由 Drift 世界叙事驱动 |
| 回旋镖推进（[Drift] advance） | 5 次，世界线树实时可见 |
| 失败任务处理 | 1 个（远处 setblock 白床）优雅跳过，**未崩** |

可观测性：
- Drift 世界线树：`GET http://127.0.0.1:8011/state` 返回任务 success/false 树。
- 技能库：`outputs/ckpt/skill/skills.json` + `code/`、`description/`、`vectordb/` 目录。
- 演化叙事：每个子任务前后 Drift 生成新的 `title/text` 与 `world_patch`（variables/mc）。

---

## 二、真正的根因（本次攻坚的最关键发现）

**历史 run5–run10 长期卡在 `list index out of range`，最终定位到一条被层层掩盖的链路：**

1. `voyager/agents/action.py` 的 `process_ai_message()` 用
   `babel = require("@babel/core")` + `require("@babel/generator")` 在 Python 侧解析 LLM 返回的 JavaScript。
2. **整个 Voyager 仓库没有安装 `@babel/core`**（`find` 全仓无 `@babel` 目录）→ `require` 立即抛异常。
3. `process_ai_message` 的 `try/except` 重试 3 次后返回**字符串** `"Error parsing action response..."`。
4. `voyager.py` 的 `step()` 判断 `isinstance(parsed_result, str)` 为真 → 调用 `self.recorder.record([], self.task)`，**传入空列表**。
5. `voyager/utils/record_utils.py` 的 `record()` 在 `events` 为空时执行 `events[0][1]["status"]...` → **IndexError** → 整个 `rollout` 崩掉，循环停滞。

> 注：早期还误判过 `/kill @s`、mineflayer 缺模块、函数未自动调用等，那些也是真实存在并已修复的问题（见第四节），
> 但**最后压死骆驼的那根稻草是 `@babel/core` 缺失导致 action 解析永远失败**。

**修复（两处，均为最小改动）：**

- `voyager/agents/action.py` 的 `process_ai_message()`：删除 babel 依赖，改用**纯 Python 正则**提取
  ```` ```javascript ```` 块里的 `async function NAME(bot){...}`，生成与原始完全相同结构的
  `{program_code, program_name, exec_code}`。这样无论 node 环境是否装 babel，解析都稳定成功。
- `voyager/utils/record_utils.py` 的 `record()`：对空 `events` 加保护——`events` 为空时给
  `init_position` 一个默认值 `[0,0]`，**任何解析失败都不会再让 recorder 崩、拖累整个学习循环**（防御性，符合"直到自然学会为止"）。

修复后 Voyager 正常执行代码 → Critic 判定 success → 技能入库 → Drift 推进叙事，**全链路打通**。

---

## 三、环境真相（务必记牢）

| 组件 | 位置 / 端口 | 说明 |
|---|---|---|
| MC 服务器 | `/Users/zxydediannao/DriftServer`，Paper 1.20.1，端口 **25565**，`online-mode=false` | bot 为 **op 4**（uuid `67128b5b-2e6b-3ad1-baa0-1b937b03e5c5`），用户名 `bot` |
| DriftSystem 后端 | FastAPI，`http://127.0.0.1:8011` | 由 run 脚本自行拉起，环境变量 `DRIFT_USE_PAYLOAD_V2=true` |
| DriftSystem 插件 | `DriftServer/plugins/DriftSystem-1.0-SNAPSHOT.jar`（端口 8010 后端） | 已 patch `isNewPlayer→false`，关闭入服自动教学 |
| mineflayer 桥 | `Voyager-main/voyager/env/mineflayer/index.js`，HTTP 端口 **3000** | 每次 rollout 软重置会重启子进程（~11s，属正常） |
| Python 环境 | `/Users/zxydediannao/.workbuddy/binaries/python/envs/voyager` | 跑 Voyager + Drift 桥 |
| Node 环境 | `/Users/zxydediannao/.workbuddy/binaries/node/versions/22.22.2/bin` | 跑 mineflayer |
| JDK | `/opt/homebrew/opt/openjdk@21/bin`（JDK 21） | 跑 MC 服务器 |
| LLM 路由 | chat/任务生成 → **DeepSeek**（`deepseek-chat`）；embeddings → **智谱/Zhipu**（`embedding-3`） | 凭据来自 shell 环境变量 `DEEPSEEK_API_KEY` / `ZHIPU_API_KEY` |

**依赖的环境变量（启动前必须已 export）：**
`DEEPSEEK_API_KEY`、`DEEPSEEK_API_BASE`、`ZHIPU_API_KEY`（或 `GLM_API_KEY`）。

---

## 四、本次及历史累计修改清单

所有修改都在本地 fork，便于复盘。

### 1. `Voyager-main/voyager/agents/action.py`（本次最关键）
- `process_ai_message()`：babel 解析 → **纯 Python 正则提取**（见第二节）。
- 顶部 `from javascript import require` 现已不再用于 babel，但保留无害。

### 2. `Voyager-main/voyager/utils/record_utils.py`（本次）
- `record()`：空 `events` 保护，避免 `events[0]` 越界崩循环。

### 3. `Voyager-main/voyager/voyager.py`（历史）
- 所有 `mode="hard"` 改为 `mode="soft"`（避免 `/kill @s` 把 bot 杀掉导致失连）。
- 软重置后追加 `env.step("bot.chat('/clear @s')")` 清空背包。

### 4. `Voyager-main/voyager/env/mineflayer/index.js`（历史）
- `evaluateCode()`：检测到"已定义但未调用"的 async 函数时**自动调用一次**（LLM 偶尔只定义不调用）。
- 修正 `minecrafthawkeye` 导出（`require(...).default` 兜底）。
- 软重置逻辑保留（不再 `/kill @s`）。

### 5. `Voyager-main/voyager/env/mineflayer/lib/observation/base.js`（历史）
- `bot.observe()`：无事件时也返回**非空结构化数组**（兜底），避免空观察导致下游 `[-1]` 越界。

### 6. `Voyager-main/voyager/env/mineflayer/node_modules/mineflayer-collectblock/`（历史）
- 该本地 `file:` 依赖缺 `lib/`，用仓库内 `tsc` 编译出 `lib/`（8 个 .js 模块），bot 才能正常 spawn。

### 7. `DriftServer/plugins/DriftSystem-1.0-SNAPSHOT.jar`（历史）
- 字节码 patch：`TutorialManager.isNewPlayer` 恒返回 `false`，关闭入服自动教学。
- 备份：`DriftSystem-1.0-SNAPSHOT.jar.bak`。jar 无签名，可安全改。

### 8. 本项目脚本 `outputs/`（本次运行入口）
- `drift_director.py`：`DriftLevelDirector`，`propose_next_task()` 推进 Drift、写世界线 ledger、生成"单步可执行 bot 动作"任务。
- `voyager_drift.py`：`DriftVoyager(Voyager)` 子类，`learn()` 接管为"Drift 驱动 + 顺序执行 + 直到学会"；`rollout()` 含重试自愈与 `traceback.print_exc()` 便于定位。
- `run_drift_voyager.py`：入口，路由 LLM、拉起 Drift 后端、注入"建小镇医院"关卡、`player_id="bot"`。

---

## 五、复现命令

```bash
# 1) 确认 MC 服务器在跑（端口 25565），若没跑先起服务器（见第三节 JDK 路径）
lsof -ti :25565 || echo "MC 服务器未启动"

# 2) 准备环境变量
export DEEPSEEK_API_KEY=...        # 必须
export DEEPSEEK_API_BASE=...       # 必须
export ZHIPU_API_KEY=...           # 必须（embeddings）

# 3) 启动闭环（后台）
cd /Users/zxydediannao/WorkBuddy/2026-08-25-16-13-39/outputs
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

## 六、残余风险 / 已知限制

1. **关卡任务偏"指令型"**：当前 Drift 生成的子任务多为 `bot.chat('/give ...')` / `/setblock`，
   属于"自然语言关卡 → 单步指令"的轻量验证。真正的"建造诊室结构 + 召唤医生 NPC + 对话救治"需要
   Drift 的 `world_patch` 真正落到 MC 世界（目前 `world_patch` 仅作为上下文/叙事，未在方块层实例化结构/NPC）。
   若要"医院真的建出来"，需扩展 `index.js` 或写专门的控制原语把 `world_patch.mc` 落成方块/实体。
2. **跨维度/远坐标任务会失败**：如 `(120,65,80)` 放床，bot 在出生点且目标未加载，Critic 判失败 → 已优雅跳过。
   可增强：让 Drift 生成"先走到目标附近再执行"的多步任务，或限制任务坐标在出生点附近。
3. **`@babel` 缺失是框架级坑**：本次用纯 Python 正则绕过。若未来需要 babel 的高级校验/转译，
   应在该 node 环境 `npm i @babel/core @babel/generator`（注意 `javascript` 包 `require` 的解析路径）。
4. **运行进程需手动管理**：脚本后台运行时，shell 退出不会杀进程（已用 `run_in_background` 拉起）。
   停止：`pkill -f run_drift_voyager.py` 并 `lsof -ti :3000 | xargs kill -9`；MC 服务器（25565）与 Drift 后端（8011）按需另管。

---

## 七、一句话总结

从 run5 到 run11 一直卡在 `list index out of range`，根因是 **Voyager 解析 LLM 返回的 JS 时依赖的
`@babel/core` 在本环境根本没装**，导致 action 永远解析失败 → 空列表传入 recorder 越界崩循环。
改用纯 Python 正则提取 + recorder 空列表保护后，run12 闭环稳定跑通：任务顺序执行、技能入库、
Drift 世界线可见演化，验收标准达成。
