#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地测试脚本：验证公众号 Cookie 登录（非阻塞 immediate 模式）
使用说明：
1) 确保已启动后端： uvicorn app.main:app --reload
2) 修改下方 CONFIG 部分（BASE_URL、EMAIL、PASSWORD），如需可设置 MAKE_ADMIN=True 以便跳过激活校验（仅本地测试用）。
3) 运行脚本： python script/cookie_login_test.py
4) 脚本会：
   - 尝试登录（不存在则自动注册）
   - 如配置 MAKE_ADMIN=True，将直接在 SQLite 数据库里把当前用户设置为 admin
   - 调用 /cookie/get 获取二维码（base64），保存为 qrcode.png 并尝试自动打开
   - 每 3 秒轮询 /cookie/poll，直到登录成功或超时
   - 打印成功信息，并展示 /cookie/list 列表
"""

import base64
import json
import os
import sys
import time
import sqlite3
import subprocess
from typing import Optional

import requests


# ============ 配置区 ============
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
EMAIL = os.getenv("TEST_EMAIL", "lucida1607@gmail.com")
PASSWORD = os.getenv("TEST_PASSWORD", "12345qwert")
DB_PATH = os.getenv("DB_PATH", os.path.join(os.getcwd(), "app.db"))  # 默认 ./app.db
MAKE_ADMIN = True  # 仅本地测试使用：将当前用户设为 admin，跳过激活校验
QR_SAVE_PATH = os.path.join(os.getcwd(), "qrcode.png")
POLL_TIMEOUT_SECONDS = 180
POLL_INTERVAL_SECONDS = 3
# ===============================


def open_image(path: str) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.call(["open", path])
        else:
            subprocess.call(["xdg-open", path])
    except Exception:
        pass


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
    # 先尝试登录
    r = s.post(f"{base}/auth/login", json={"email": email, "password": password}, timeout=10)
    if r.status_code == 200:
        token = r.json().get("access_token")
        print("[OK] 登录成功")
        return token

    # 不存在则注册
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
        # 可能是密码错误或其它错误
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        print(f"[ERR] 注册失败：{r.status_code} {detail}")
        return None


def save_qr(qr_base64: str, path: str) -> None:
    # 防御性：去掉 data:image/png;base64, 前缀（如果有的话）
    if qr_base64.startswith("data:image/"):
        hdr, b64 = qr_base64.split(",", 1)
    else:
        b64 = qr_base64
    data = base64.b64decode(b64)
    with open(path, "wb") as f:
        f.write(data)


def main() -> None:
    print("==== Cookie 登录（immediate 模式）测试 ====")
    print(f"BASE_URL={BASE_URL}")
    print(f"EMAIL={EMAIL}")
    token = login_or_register(BASE_URL, EMAIL, PASSWORD)
    if not token:
        print("[ERR] 无法登录，退出")
        return

    if MAKE_ADMIN:
        ensure_admin(EMAIL, DB_PATH)

    headers = {"Authorization": f"Bearer {token}"}

    # 1) 获取二维码与 login_key（立即返回，不阻塞）
    print("[1/3] 调用 /cookie/get 获取二维码…")
    r = requests.get(f"{BASE_URL}/cookie/get?inline_qr=true", headers=headers, timeout=30)
    if r.status_code != 200:
        print(f"[ERR] /cookie/get 返回 {r.status_code}: {r.text}")
        return
    data = r.json()
    print("响应：", json.dumps(data, ensure_ascii=False))

    login_key = data.get("login_key")
    qr_b64 = data.get("qrcode_base64")
    if not login_key or not qr_b64:
        print("[ERR] 未获取到 login_key 或二维码。请检查服务端日志与网络连通性。")
        return

    # 保存二维码
    try:
        save_qr(qr_b64, QR_SAVE_PATH)
        print(f"[OK] 二维码已保存到：{QR_SAVE_PATH}")
        open_image(QR_SAVE_PATH)
    except Exception as e:
        print(f"[WARN] 保存/打开二维码失败：{e}")

    # 2) 轮询 /cookie/poll
    print("[2/3] 开始轮询 /cookie/poll … 请使用微信扫码并在手机确认")
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    last_msg = None
    while time.time() < deadline:
        rp = requests.get(f"{BASE_URL}/cookie/poll", params={"login_key": login_key}, headers=headers, timeout=30)
        if rp.status_code != 200:
            print(f"[ERR] /cookie/poll 返回 {rp.status_code}: {rp.text}")
            return
        body = rp.json()
        status = body.get("status")
        msg = body.get("message")
        if msg and msg != last_msg:
            print("状态：", msg)
            last_msg = msg
        if status == "success":
            cookie_obj = body.get("cookie")
            print("[OK] 登录成功！")
            print("Cookie 记录：", json.dumps(cookie_obj, ensure_ascii=False, indent=2))
            break
        elif status == "pending":
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        else:
            print("[ERR] 登录失败：", json.dumps(body, ensure_ascii=False))
            return
    else:
        print("[ERR] 轮询超时，未完成扫码确认")
        return

    # 3) 列表验证
    print("[3/3] 调用 /cookie/list 验证…")
    rl = requests.get(f"{BASE_URL}/cookie/list", headers=headers, timeout=30)
    if rl.status_code != 200:
        print(f"[WARN] /cookie/list 返回 {rl.status_code}: {rl.text}")
    else:
        print("有效 Cookie 列表：", json.dumps(rl.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
