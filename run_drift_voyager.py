#!/usr/bin/env python3
"""
入口：把 Drift 作为 Voyager 的关卡 Director，连真实 MC 世界(25565)跑闭环。

流程：
  1. 路由 LLM：对话/任务生成 -> DeepSeek；向量库 embedding -> 智谱(Zhipu, 有 embedding 接口)
  2. 自启 Drift 后端(8011，使用环境变量里有效的 DeepSeek key)
  3. 构造 DriftVoyager，自然语言注入「小镇医院」关卡
  4. 跑 learn() 闭环：Drift 出任务 -> Voyager 在世界里执行 -> 成败回灌 Drift 演化世界线
  5. 输出世界线 ledger，供观察演化

运行：
  export PATH=/Users/zxydediannao/.workbuddy/binaries/node/versions/22.22.2/bin:$PATH
  /Users/zxydediannao/.workbuddy/binaries/python/envs/voyager/bin/python run_drift_voyager.py
"""

import os
import sys
import time
import json
import subprocess
import requests

# ---------------------------------------------------------------------------
# 1. LLM 路由
# ---------------------------------------------------------------------------
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
ZHIPU_BASE = os.environ.get("ZHIPU_API_BASE") or "https://open.bigmodel.cn/api/paas/v4"
ZHIPU_KEY = os.environ.get("GLM_API_KEY") or os.environ.get("ZHIPU_API_KEY") or ""

if not DEEPSEEK_KEY:
    raise SystemExit("缺少 DEEPSEEK_API_KEY 环境变量")

os.environ["OPENAI_API_KEY"] = DEEPSEEK_KEY
os.environ["OPENAI_API_BASE"] = DEEPSEEK_BASE
os.environ["OPENAI_MODEL"] = "deepseek-chat"

# ---------------------------------------------------------------------------
# 2. 启动 Drift 后端(8011)，使用有效的 DeepSeek key 覆盖 .env 里的失效 key
# ---------------------------------------------------------------------------
DRIFT_BACKEND = os.path.expanduser("~/Downloads/drift-system-0.1-stable/backend")
VENV_PY = "/Users/zxydediannao/.workbuddy/binaries/python/envs/drift/bin/python"

# 清掉可能占着 8011 的旧实例
os.system("lsof -ti :8011 2>/dev/null | xargs -r kill -9 2>/dev/null || true")
time.sleep(1)

be_env = dict(os.environ)
be_env["OPENAI_API_KEY"] = DEEPSEEK_KEY
be_env["OPENAI_BASE_URL"] = DEEPSEEK_BASE
be_env["OPENAI_MODEL"] = "deepseek-chat"
be_env["DRIFT_USE_PAYLOAD_V2"] = "true"
be_env["DRIFT_DEBUG_TRACE"] = "true"

backend_log = open("/tmp/drift_8011_run.log", "w")
backend_proc = subprocess.Popen(
    [VENV_PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8011"],
    cwd=DRIFT_BACKEND,
    env=be_env,
    stdout=backend_log,
    stderr=subprocess.STDOUT,
)


def wait_port(port=8011, timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = requests.get(f"http://127.0.0.1:{port}/", timeout=3)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


print("[run] 等待 Drift 后端(8011)就绪 ...")
if not wait_port(8011, 90):
    print("[run] Drift 后端启动失败，日志见 /tmp/drift_8011_run.log")
    backend_proc.terminate()
    raise SystemExit(1)
print("[run] Drift 后端已就绪")

# ---------------------------------------------------------------------------
# 3. 把向量库 embedding 路由到智谱(DeepSeek 无 embedding 接口)
#    必须在 import voyager 之前打补丁
# ---------------------------------------------------------------------------
import langchain.embeddings.openai as _oa


class ZhipuEmbeddings(_oa.OpenAIEmbeddings):
    def __init__(self, **kw):
        # 安装的是 community 版 OpenAIEmbeddings，实际模型参数名为 model
        kw.setdefault("model", "embedding-3")
        kw.setdefault("model_name", "embedding-3")  # 兼容 monolithic langchain
        kw.setdefault("openai_api_base", ZHIPU_BASE)
        kw.setdefault("openai_api_key", ZHIPU_KEY)
        super().__init__(**kw)


_oa.OpenAIEmbeddings = ZhipuEmbeddings

sys.path.insert(0, os.path.expanduser("~/Downloads/Voyager-main"))
from drift_director import DriftLevelDirector
from voyager_drift import DriftVoyager

# ---------------------------------------------------------------------------
# 4. 自然语言注入「小镇医院」关卡
# ---------------------------------------------------------------------------
HOSPITAL_LEVEL = (
    "建一个小镇医院：一间诊室，一位医生NPC，患者缺少白色羊毛绷带。"
    "让 Voyager 学习搭建诊所、获取羊毛、与医生对话完成救治，并观察医院的演化。"
)

director = DriftLevelDirector(
    drift_base="http://127.0.0.1:8011",
    player_id="bot",
    level_text=HOSPITAL_LEVEL,
    level_title="小镇医院",
)

voyager = DriftVoyager(
    mc_port=25565,
    openai_api_key=DEEPSEEK_KEY,
    action_agent_model_name="deepseek-chat",
    curriculum_agent_model_name="deepseek-chat",
    curriculum_agent_qa_model_name="deepseek-chat",
    critic_agent_model_name="deepseek-chat",
    skill_manager_model_name="deepseek-chat",
    max_iterations=15,
    action_agent_task_max_retries=3,
    env_request_timeout=240,
    ckpt_dir="ckpt",
)
voyager.drift = director

# ---------------------------------------------------------------------------
# 5. 跑闭环
# ---------------------------------------------------------------------------
print("\n########## 开始 Drift × Voyager 闭环(自然语言注入医院关卡) ##########\n")
result = None
try:
    result = voyager.learn()
finally:
    print("\n########## 闭环结束，关闭 Drift 后端 ##########")
    try:
        if result:
            print("RESULT:", json.dumps(
                {k: (v if k != "world_line" else "<见 /add ledger>")
                 for k, v in result.items()},
                ensure_ascii=False, default=str)[:1500])
    except Exception as e:
        print("result print error:", e)
    backend_proc.terminate()
    try:
        backend_proc.wait(timeout=10)
    except Exception:
        backend_proc.kill()
