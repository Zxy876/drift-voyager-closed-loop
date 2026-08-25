#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测智谱(Zhipu) GLM OpenAI 兼容端点是否可用且返回合法 JSON。"""
import os
import requests

key = os.getenv("GLM_API_KEY")
print("GLM_API_KEY 可见? 长度 =", len(key) if key else 0)

base = "https://open.bigmodel.cn/api/compat/v1"
model = "glm-4-flash"
payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": "只允许输出 JSON 对象，禁止任何解释文字。"},
        {"role": "user", "content": '返回 {"structure_type":"house","width":7}'},
    ],
    "temperature": 0,
    "response_format": {"type": "json_object"},
    "max_tokens": 200,
}
try:
    r = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=(15, 40),
    )
    print("HTTP", r.status_code)
    print("BODY:", r.text[:600])
    try:
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        import json as _j
        print("解析 content:", repr(content[:200]))
        _j.loads(content)
        print("json.loads OK")
    except Exception as e:
        print("解析失败:", type(e).__name__, e)
except Exception as e:
    print("请求异常:", type(e).__name__, e)
