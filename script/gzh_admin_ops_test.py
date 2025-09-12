#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地测试脚本：验证 gzhaccount/gzharticle 的 show/change/delete/list 接口
使用说明：
1) 确保已启动后端： uvicorn app.main:app --reload
2) 修改下方 CONFIG（BASE_URL、EMAIL、PASSWORD、TARGET_ACCOUNT_NAME、TARGET_ARTICLE_URL 等）
3) 运行脚本： python script/gzh_admin_ops_test.py
脚本会：
  - 登录（不存在则注册）并可选设为 admin
  - 依次测试：
    /gzhaccount/show, /gzhaccount/list, /gzhaccount/change（软字段）, /gzhaccount/delete（注：删除后需谨慎）
    /gzharticle/show, /gzharticle/list, /gzharticle/change（软字段）, /gzharticle/delete
  - 注意：删除接口会真实删除，请在测试前确认
"""

import json
import os
import sqlite3
import time
from typing import Optional

import requests

# ============ 配置区 ============
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
EMAIL = os.getenv("TEST_EMAIL", "lucida1607@gmail.com")
PASSWORD = os.getenv("TEST_PASSWORD", "12345qwert")
DB_PATH = os.getenv("DB_PATH", os.path.join(os.getcwd(), "app.db"))
MAKE_ADMIN = True  # 本地测试可置 True

# 目标测试数据（请根据你实际库中的数据设置）
TARGET_ACCOUNT_NAME = os.getenv("TARGET_ACCOUNT_NAME", "哥飞")
TARGET_ACCOUNT_BIZ = os.getenv("TARGET_ACCOUNT_BIZ", "")  # 可留空
TARGET_ARTICLE_URL = os.getenv("TARGET_ARTICLE_URL", "")  # 可留空
NEW_DESCRIPTION = os.getenv("NEW_DESCRIPTION", "测试描述-修改于脚本")
NEW_ARTICLE_TITLE = os.getenv("NEW_ARTICLE_TITLE", "脚本测试修改标题")
# ===============================


def ensure_admin(email: str, db_path: str) -> None:
    if not os.path.exists(db_path):
        print(f"[WARN] 未找到数据库文件：{db_path}，跳过 admin 设置")
        return
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("UPDATE accounts SET role='admin' WHERE email=?", (email,))
        conn.commit()
        conn.close()
        print(f"[OK] 已将 {email} 设为 admin")
    except Exception as e:
        print(f"[WARN] 设置 admin 失败：{e}")


def login_or_register(base: str, email: str, password: str) -> Optional[str]:
    s = requests.Session()
    r = s.post(f"{base}/auth/login", json={"email": email, "password": password}, timeout=10)
    if r.status_code == 200:
        print("[OK] 登录成功")
        return r.json().get("access_token")
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


def api_post(path: str, token: str, body: dict) -> requests.Response:
    url = f"{BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=body, timeout=30)
    return r


def main() -> None:
    print("==== gzhaccount/gzharticle 管理接口测试 ====")
    print(f"BASE_URL={BASE_URL}")
    print(f"EMAIL={EMAIL}")

    token = login_or_register(BASE_URL, EMAIL, PASSWORD)
    if not token:
        print("[ERR] 无法登录，退出")
        return
    if MAKE_ADMIN:
        ensure_admin(EMAIL, DB_PATH)

    # 1) 账号 show
    print("\n[1] /gzhaccount/show by name")
    r = api_post("/gzhaccount/show", token, {"name": TARGET_ACCOUNT_NAME})
    print(r.status_code, r.text)

    # 2) 账号 list（管理员可传 owner_email，普通用户会被忽略）
    print("\n[2] /gzhaccount/list (分页)")
    r = api_post("/gzhaccount/list", token, {"offset": 0, "limit": 5})
    print(r.status_code, r.text)

    # 3) 账号 change（不改唯一键，仅改描述）
    print("\n[3] /gzhaccount/change (修改描述)")
    r = api_post("/gzhaccount/change", token, {"name": TARGET_ACCOUNT_NAME, "description": NEW_DESCRIPTION})
    print(r.status_code, r.text)

    # 4) 文章 list（按账号筛）
    print("\n[4] /gzharticle/list by mp_account")
    r = api_post("/gzharticle/list", token, {"mp_account": TARGET_ACCOUNT_NAME, "offset": 0, "limit": 5})
    print(r.status_code, r.text)

    # 5) 文章 show（如果给了 URL）
    if TARGET_ARTICLE_URL:
        print("\n[5] /gzharticle/show by url")
        r = api_post("/gzharticle/show", token, {"url": TARGET_ARTICLE_URL})
        print(r.status_code, r.text)

        # 6) 文章 change（软字段：修改标题）
        print("\n[6] /gzharticle/change (修改标题)")
        r = api_post("/gzharticle/change", token, {"url": TARGET_ARTICLE_URL, "title": NEW_ARTICLE_TITLE})
        print(r.status_code, r.text)

        # 7) 文章 delete（请谨慎）
        print("\n[7] /gzharticle/delete by url (谨慎)")
        r = api_post("/gzharticle/delete", token, {"url": TARGET_ARTICLE_URL})
        print(r.status_code, r.text)

    # 8) 账号 delete（谨慎：会级联删除文章）——如需测试请取消注释
    # print("\n[8] /gzhaccount/delete by name (谨慎：会级联删除文章)")
    # r = api_post("/gzhaccount/delete", token, {"name": TARGET_ACCOUNT_NAME})
    # print(r.status_code, r.text)


if __name__ == "__main__":
    main()
