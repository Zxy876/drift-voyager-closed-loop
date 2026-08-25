#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测 Drift 后端实际使用的 LLM 端点返回了什么。"""
import os
import sys
import json
import requests
from dotenv import load_dotenv

ENV_PATH = "/Users/zxydediannao/Downloads/drift-system-0.1-stable/backend/.env"
load_dotenv(ENV_PATH)

KEY = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
BASE = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")

print(f"BASE_URL = {BASE}")
print(f"MODEL    = {MODEL}")
print(f"KEY?     = {'yes(%d位)' % len(KEY) if KEY else 'NO'}")

payload = {
    "model": MODEL,
    "messages": [
        {"role": "system", "content": "只允许输出 JSON 对象，禁止任何解释文字。"},
        {"role": "user", "content": '返回 {"structure_type":"house","width":7}'},
    ],
    "temperature": 0,
    "response_format": {"type": "json_object"},
    "max_tokens": 200,
}

print("\n--- 直接打 /chat/completions ---")
try:
    r = requests.post(
        f"{BASE}/chat/completions",
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=(15, 40),
    )
    print("HTTP", r.status_code)
    print("RAW BODY (前 1200 字符):")
    print(r.text[:1200])
    # 尝试按 spec_llm_v1 的方式解析
    try:
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        print("\n解析出的 content:", repr(content[:400]))
        try:
            parsed = json.loads(content)
            print("json.loads OK ->", parsed)
        except Exception as je:
            print("json.loads FAILED ->", type(je).__name__, je)
    except Exception as e:
        print("响应体不是合法 JSON:", type(e).__name__, e)
except Exception as e:
    print("请求异常:", type(e).__name__, e)
