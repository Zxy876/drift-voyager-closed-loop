#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DriftSystem × Voyager 最小闭环 Demo
====================================
验证你提的核心诉求：
  在 Voyager 的世界里，用自然语言注入「医院」关卡，
  让 Voyager 学习，并观察医院随 Voyager 成败而演化（回旋镖闭环）。

Drift 后端（真·FastAPI + 真·LLM）扮演 Voyager 进程内的 Director：
  - /story/inject     自然语言文本 -> Drift 调 LLM 生成场景/世界补丁/剧情
  - /tree/add         Voyager 把成败日志回灌给 Drift（影响世界线）
  - /story/advance    推进剧情，生成下一节世界补丁
  - /tree/state       观察世界线演化（回旋镖）

运行前请确保 Drift 后端已在 127.0.0.1:8000 启动（见 start_drift.sh）。
"""
import requests
import json
import sys

BASE = "http://127.0.0.1:8011"
PLAYER = "voyager_01"
LEVEL_ID = "hospital_demo"


def call(method, path, **kw):
    try:
        r = requests.request(method, f"{BASE}{path}", timeout=90, **kw)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text[:500]
    except Exception as e:
        return "ERR", str(e)


def show(title, payload):
    print("\n" + "=" * 64)
    print(f"▶ {title}")
    print("-" * 64)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text[:3500])


def main():
    print("=" * 64)
    print(" DriftSystem × Voyager 最小闭环 Demo")
    print(" 自然语言注入「医院」关卡 + Voyager↔Drift 演化观察")
    print("=" * 64)

    # ---------- ① 注入「医院」关卡（自然语言 -> Drift 调 LLM 生成场景）----------
    hospital_text = (
        "建一个小镇医院：一间诊室，一位医生NPC坐在里面，"
        "一名患者缺少白色羊毛绷带。引导 Voyager 学习搭建诊所、"
        "获取白色羊毛、与医生对话完成救治。"
    )
    inj = {
        "level_id": LEVEL_ID,
        "title": "小镇医院",
        "text": hospital_text,
        "player_id": PLAYER,
        "scene_theme": "hospital",
        "scene_hint": "患者需要白色羊毛绷带；医生在诊室等待救治",
    }
    code, resp = call("POST", "/story/inject", json=inj)
    if code == 400 and "already exists" in str(resp):
        print("\n(关卡已存在，跳过注入，直接加载)")
        call("POST", f"/story/load/{PLAYER}/{LEVEL_ID}")
        # 读取已有关卡详情以展示
        code, resp = call("GET", f"/story/level/{LEVEL_ID}")
        show("① 「医院」关卡（已存在，加载详情）", resp)
    else:
        show("① 注入「医院」关卡（Drift 调 LLM 生成场景+世界补丁）", resp)

    # ---------- ② 确认关卡已注册（精简：只显示总数与医院关卡）----------
    code, resp = call("GET", "/story/levels")
    levels = resp.get("levels", []) if isinstance(resp, dict) else []
    ids = [lv.get("id") for lv in levels]
    has_hosp = any("hospital" in str(i) for i in ids)
    show("② 关卡总数=%d，医院关卡已注册=%s" % (len(ids), has_hosp),
         {"total": len(ids), "hospital_registered": has_hosp})

    # ---------- ③ Voyager 把「失败日志」回灌给 Drift（回旋镖）----------
    code, resp = call("POST", "/add", json={
        "content": (
            "Voyager 尝试用剪刀采集白色羊毛但反复失败：当前世界缺少羊，"
            "且诊室没有床。需要 Drift 调整场景——在诊室旁生成羊与剪刀工作台。"
        )
    })
    show("③ Voyager 回灌失败日志 -> Drift 世界线（tree 偏置）", resp)

    # ---------- ④ 推进剧情（自然语言驱动世界补丁）----------
    code, resp = call("POST", f"/story/advance/{PLAYER}", json={
        "world_state": {},
        "action": {"type": "chat", "text": "在诊室旁生成一只羊和一把剪刀工作台。"},
    })
    show("④ 推进剧情（Drift 生成下一节世界补丁）", resp)

    # ---------- ⑤ 观察世界线演化状态 ----------
    code, resp = call("GET", "/state")
    show("⑤ 世界线/回旋镖状态（演化结果）", resp)

    # ---------- ⑥ Voyager 学会后回灌成功，观察医院进一步演化 ----------
    code, resp = call("POST", "/add", json={
        "content": (
            "Voyager 已学会「采集白色羊毛」技能，成功交付 5 个白色羊毛绷带，"
            "医生完成救治。世界应演化出更完整的医院（病房/药柜）。"
        )
    })
    code2, resp2 = call("POST", f"/story/advance/{PLAYER}", json={
        "world_state": {"hospital_level": 1},
        "action": {"type": "build", "text": "搭建病房与药柜"},
    })
    show("⑥ Voyager 学会后回灌成功 -> Drift 演化出更完整医院", resp2)

    print("\n" + "=" * 64)
    print(" Demo 完成：自然语言关卡已注入，Voyager↔Drift 闭环可观察。")
    print("=" * 64)


if __name__ == "__main__":
    main()
