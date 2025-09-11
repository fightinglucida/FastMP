#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地测试脚本：验证 /cookie/list、/cookie/change、/cookie/delete 接口
使用说明：
1) 确保已启动后端： uvicorn app.main:app --reload
2) 建议先运行 script/cookie_login_test.py 至少登录一次（最好2次，便于切换）
3) 修改下方 CONFIG（BASE_URL、EMAIL、PASSWORD、MAKE_ADMIN 等）
4) 运行脚本： python script/cookie_manage_test.py
5) 脚本流程：
   - 登录/注册（可选设为管理员）
   - 列出当前账号下有效 cookies
   - 交互式选择一个 token 切换为当前
   - 可选：选择一个 token 删除
"""

import json
import os
import sqlite3
import sys
from typing import Optional

import requests

# ============ 配置区 ============
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
EMAIL = os.getenv("TEST_EMAIL", "lucida1607@gmail.com")
PASSWORD = os.getenv("TEST_PASSWORD", "12345qwert")
DB_PATH = os.getenv("DB_PATH", os.path.join(os.getcwd(), "app.db"))  # 默认 ./app.db
MAKE_ADMIN = True  # 仅本地测试使用：将当前用户设为 admin，跳过激活校验
# ===============================


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


def login_or_register(base: str, email: str, password: str) -> Optional[str]:
    s = requests.Session()
    r = s.post(f"{base}/auth/login", json={"email": email, "password": password}, timeout=10)
    if r.status_code == 200:
        token = r.json().get("access_token")
        print("[OK] 登录成功")
        return token
    r = s.post(f"{base}/auth/register", json={"email": email, "password": password}, timeout=10)
    if r.status_code in (200, 201):
        print("[OK] 注册成功，准备登录…")
        r = s.post(f"{base}/auth/login", json={"email": email, "password": password}, timeout=10)
        if r.status_code == 200:
            token = r.json().get("access_token")
            print("[OK] 登录成功")
            return token
        print(f"[ERR] 登录失败：{r.status_code} {r.text}")
        return None
    else:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        print(f"[ERR] 注册失败：{r.status_code} {detail}")
        return None


def list_cookies(base: str, token: str) -> list:
    r = requests.get(f"{base}/cookie/list", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if r.status_code != 200:
        print(f"[ERR] /cookie/list 返回 {r.status_code}: {r.text}")
        return []
    data = r.json().get("items", [])
    print("\n=== 有效 Cookie 列表 ===")
    if not data:
        print("(空)")
    for i, item in enumerate(data, 1):
        print(f"[{i}] token={item.get('token')} is_current={item.get('is_current')} name={item.get('name','')} ")
    return data


def change_cookie(base: str, token: str, target_token: str) -> bool:
    r = requests.post(
        f"{base}/cookie/change",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"token": target_token},
        timeout=20,
    )
    if r.status_code == 200:
        print("[OK] 切换成功：", r.json())
        return True
    print(f"[ERR] 切换失败：{r.status_code} {r.text}")
    return False


def delete_cookie(base: str, token: str, target_token: str) -> bool:
    r = requests.post(
        f"{base}/cookie/delete",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"token": target_token},
        timeout=20,
    )
    if r.status_code == 200:
        print("[OK] 删除成功")
        return True
    print(f"[ERR] 删除失败：{r.status_code} {r.text}")
    return False


def main() -> None:
    print("==== Cookie 管理接口测试 ====")
    print(f"BASE_URL={BASE_URL}")
    print(f"EMAIL={EMAIL}")
    token = login_or_register(BASE_URL, EMAIL, PASSWORD)
    if not token:
        print("[ERR] 无法登录，退出")
        return

    if MAKE_ADMIN:
        ensure_admin(EMAIL, DB_PATH)

    # 1) 列表
    items = list_cookies(BASE_URL, token)
    if not items:
        print("[WARN] 当前无有效 cookie。请先运行 script/cookie_login_test.py 再试。")
        return

    # 2) 切换
    try:
        idx = int(input("\n输入要切换的序号（回车跳过切换）：") or 0)
    except Exception:
        idx = 0
    if idx and 1 <= idx <= len(items):
        target = items[idx - 1].get("token")
        if target:
            change_cookie(BASE_URL, token, target)
            # 切换后再次查看列表
            list_cookies(BASE_URL, token)

    # 3) 删除
    try:
        idx_d = int(input("\n输入要删除的序号（回车跳过删除）：") or 0)
    except Exception:
        idx_d = 0
    if idx_d and 1 <= idx_d <= len(items):
        target_d = items[idx_d - 1].get("token")
        confirm = input(f"确认删除 token={target_d}? 输入 'YES' 确认：")
        if confirm.strip().upper() == "YES":
            delete_cookie(BASE_URL, token, target_d)
            # 删除后再次查看列表
            list_cookies(BASE_URL, token)
        else:
            print("已取消删除。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断。")
