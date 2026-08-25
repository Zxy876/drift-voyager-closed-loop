#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐个探测候选 LLM 端点，找出当前真正可用的那个。"""
import os
import json
import requests

GLM = os.getenv("GLM_API_KEY")
DS_KEY = os.getenv("DEEPSEEK_API_KEY")
DS_BASE = os.getenv("DEEPSEEK_API_BASE") or "https://api.deepseek.com/v1"

print(f"GLM_API_KEY len={len(GLM) if GLM else 0}  DS_KEY len={len(DS_KEY) if DS_KEY else 0}  DS_BASE={DS_BASE}")

candidates = []

# 智谱系列（先不带 response_format，因为智谱可能不支持）
for m in ["glm-4-flash", "glm-4-plus", "glm-4", "glm-4-air"]:
    candidates.append({
        "name": f"zhipu:{m}",
        "base": "https://open.bigmodel.cn/api/compat/v1",
        "key": GLM, "model": m, "rf": False,
    })

# 环境变量里的 deepseek（带/不带 response_format 各试）
for rf in [True, False]:
    candidates.append({
        "name": f"deepseek-env:deepseek-chat(rf={rf})",
        "base": DS_BASE, "key": DS_KEY, "model": "deepseek-chat", "rf": rf,
    })


def try_one(c):
    if not c["key"]:
        return f"[{c['name']}] 无 key，跳过"
    payload = {
        "model": c["model"],
        "messages": [
            {"role": "system", "content": "只允许输出JSON对象，禁止解释文字。"},
            {"role": "user", "content": '返回 {"structure_type":"house","width":7}'},
        ],
        "temperature": 0,
        "max_tokens": 120,
    }
    if c["rf"]:
        payload["response_format"] = {"type": "json_object"}
    try:
        r = requests.post(
            f"{c['base']}/chat/completions",
            headers={"Authorization": f"Bearer {c['key']}", "Content-Type": "application/json"},
            json=payload, timeout=(15, 40),
        )
        if r.status_code == 200:
            try:
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                json.loads(content)
                return f"[{c['name']}] ✅ HTTP200 合法JSON -> {content[:80]}"
            except Exception as e:
                return f"[{c['name']}] ⚠️ HTTP200 但解析失败: {r.text[:120]}"
        return f"[{c['name']}] ❌ HTTP{r.status_code} {r.text[:120]}"
    except Exception as e:
        return f"[{c['name']}] ❌ 异常 {type(e).__name__}: {e}"


print("\n=== 探测结果 ===")
for c in candidates:
    print(try_one(c))
