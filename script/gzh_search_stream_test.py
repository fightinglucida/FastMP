#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地测试脚本：验证 /gzhaccount/search/stream 流式接口（NDJSON）
使用说明：
1) 确保已启动后端： uvicorn app.main:app --reload
2) 如有需要，修改下方 CONFIG（BASE_URL、EMAIL、PASSWORD、NAME、MAX_ARTICLES）。
3) 运行脚本： python script/gzh_search_stream_test.py
脚本会：
  - 尝试登录（不存在则自动注册）
  - 可选：将用户设为 admin（便于本地跳过激活校验，可关闭）
  - 调用 /gzhaccount/search/stream 并逐行打印事件摘要
"""

import json
import os
import sqlite3
import sys
import time
import subprocess

import requests

# ============ 配置区 ============
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
EMAIL = os.getenv("TEST_EMAIL", "lucida1607@gmail.com")
PASSWORD = os.getenv("TEST_PASSWORD", "12345qwert")
DB_PATH = os.getenv("DB_PATH", os.path.join(os.getcwd(), "app.db"))  # 默认 ./app.db
MAKE_ADMIN = True  # 仅本地测试：将当前用户设为 admin，跳过激活校验
NAME = os.getenv("GZH_NAME", "哥飞")  # 要搜索的公众号名称
MAX_ARTICLES = int(os.getenv("MAX_ARTICLES", "50"))
# ===============================

# 详细打印（可通过环境变量 PRINT_DETAILS=false 关闭）
PRINT_DETAILS = os.getenv("PRINT_DETAILS", "true").lower() in ("1", "true", "yes")
# 可选：将原始 NDJSON 事件保存到文件（为空则不保存）
SAVE_STREAM_PATH = os.getenv("SAVE_STREAM_PATH", "")


def ensure_admin(email: str, db_path: str) -> None:
    if not os.path.exists(db_path):
        print(f"[WARN] 未找到数据库文件：{db_path}，将跳过 admin 设置")
        return
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("UPDATE accounts SET role='admin' WHERE email=?", (email,))
        conn.commit()
        conn.close()
        print(f"[OK] 已将 {email} 设置为 admin（仅本地测试）")
    except Exception as e:
        print(f"[WARN] 设置 admin 失败：{e}")


def login_or_register(base: str, email: str, password: str) -> str | None:
    s = requests.Session()
    r = s.post(f"{base}/auth/login", json={"email": email, "password": password}, timeout=10)
    if r.status_code == 200:
        print("[OK] 登录成功")
        return r.json().get("access_token")
    # 自动注册
    r = s.post(f"{base}/auth/register", json={"email": email, "password": password}, timeout=10)
    if r.status_code in (200, 201):
        print("[OK] 注册成功，准备登录…")
        r2 = s.post(f"{base}/auth/login", json={"email": email, "password": password}, timeout=10)
        if r2.status_code == 200:
            print("[OK] 登录成功")
            return r2.json().get("access_token")
        print(f"[ERR] 登录失败：{r2.status_code} {r2.text}")
        return None
    try:
        detail = r.json()
    except Exception:
        detail = r.text
    print(f"[ERR] 注册失败：{r.status_code} {detail}")
    return None


def print_event(evt: dict) -> None:
    t = evt.get("type")
    if t == "account":
        acc = evt.get("account") or {}
        print(f"[account] name={acc.get('name')} biz={acc.get('biz')} total_db={acc.get('article_account')}")
    elif t == "page":
        page = evt.get("page")
        new_added = evt.get("new_added")
        total_db = evt.get("total_db")
        has_more = evt.get("has_more")
        items = evt.get("items") or []
        latest = items[0]["title"] if items else "-"
        print(f"[page {page}] new_added={new_added} total_db={total_db} has_more={has_more} latest='{latest}' items={len(items)}")
        if PRINT_DETAILS and items:
            for i, it in enumerate(items[:10], start=1):  # 默认打印前10条详情
                print(f"    #{i} | {it.get('publish_date')} | {it.get('title')}\n      url={it.get('url')}\n      cover={it.get('cover_url')}\n      item_show_type={it.get('item_show_type')}")
            if len(items) > 10:
                print(f"    ... 共 {len(items)} 条，已省略 {len(items) - 10} 条")
    elif t == "done":
        total_db = evt.get("total_db")
        items = evt.get("items") or []
        latest = items[0]["title"] if items else "-"
        acc = evt.get("account") or {}
        print(f"[done] total_db={total_db} final_items={len(items)} latest='{latest}' account={acc.get('name')}({acc.get('biz')})")
        if PRINT_DETAILS and items:
            print("== 最终列表（最多显示前20条） ==")
            for i, it in enumerate(items[:20], start=1):
                print(f"    #{i} | {it.get('publish_date')} | {it.get('title')}\n      url={it.get('url')}\n      cover={it.get('cover_url')}\n      item_show_type={it.get('item_show_type')}")
            if len(items) > 20:
                print(f"    ... 共 {len(items)} 条，已省略 {len(items) - 20} 条")
    elif t == "error":
        print(f"[error] {evt.get('message')}")
    else:
        print(f"[unknown] {evt}")


def main() -> None:
    print("==== /gzhaccount/search/stream 测试 ====")
    print(f"BASE_URL={BASE_URL}")
    print(f"EMAIL={EMAIL}")
    print(f"GZH_NAME={NAME}")

    token = login_or_register(BASE_URL, EMAIL, PASSWORD)
    if not token:
        print("[ERR] 无法登录，退出")
        return

    if MAKE_ADMIN:
        ensure_admin(EMAIL, DB_PATH)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/x-ndjson",
    }
    payload = {"name": NAME, "max_articles": MAX_ARTICLES}
    url = f"{BASE_URL}/gzhaccount/search/stream"

    print(f"POST {url} name={NAME} max={MAX_ARTICLES}")
    with requests.post(url, headers=headers, json=payload, stream=True) as r:
        if r.status_code != 200:
            print(f"[ERR] {r.status_code} {r.text}")
            return
        print("已连接，开始接收流式事件（按行输出）。按 Ctrl+C 退出。\n")
        try:
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    print(f"! 非JSON行：{line}")
                    continue
                print_event(evt)
        except KeyboardInterrupt:
            print("\n用户中断。")


if __name__ == "__main__":
    main()
