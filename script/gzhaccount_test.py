#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键测试脚本：公众号搜索与文章列表
功能：
- 通过邮箱/密码登录（不存在则注册），可选设为管理员以便跳过激活校验
- 调用 /gzhaccount/search 进行账号搜索与文章抓取
- 调用 /gzhaccount/list 分页获取本地数据库文章
- 将结果保存为 JSON 文件：gzh_<name>_search.json 与 gzh_<name>_list.json
使用方法：
  python script/gzhaccount_test.py
脚本会交互式询问邮箱、密码、公众号名称、抓取数量、分页参数。
可使用环境变量覆盖默认：BASE_URL, TEST_EMAIL, TEST_PASSWORD, DB_PATH, MAKE_ADMIN
"""
import json
import os
import sqlite3
import sys
from typing import Optional

import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
DEFAULT_EMAIL = os.getenv("TEST_EMAIL", "lucida1607@gmail.com")
DEFAULT_PASSWORD = os.getenv("TEST_PASSWORD", "12345qwert")
DB_PATH = os.getenv("DB_PATH", os.path.join(os.getcwd(), "app.db"))
MAKE_ADMIN = os.getenv("MAKE_ADMIN", "true").lower() in ("1", "true", "yes")


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
    # 登录
    r = s.post(f"{base}/auth/login", json={"email": email, "password": password}, timeout=15)
    if r.status_code == 200:
        return r.json().get("access_token")
    # 注册
    r = s.post(f"{base}/auth/register", json={"email": email, "password": password}, timeout=15)
    if r.status_code in (200, 201):
        r = s.post(f"{base}/auth/login", json={"email": email, "password": password}, timeout=15)
        if r.status_code == 200:
            return r.json().get("access_token")
        print(f"[ERR] 登录失败：{r.status_code} {r.text}")
        return None
    else:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        print(f"[ERR] 注册失败：{r.status_code} {detail}")
        return None


def prompt(msg: str, default: Optional[str] = None) -> str:
    s = input(f"{msg} [{'默认: ' + default if default else '必填'}]: ")
    if not s and default is not None:
        return default
    return s


def main() -> None:
    print("==== 公众号搜索与列表 测试脚本 ====")
    print(f"BASE_URL={BASE_URL}")

    email = prompt("输入邮箱", DEFAULT_EMAIL)
    password = prompt("输入密码", DEFAULT_PASSWORD)

    token = login_or_register(BASE_URL, email, password)
    if not token:
        print("[ERR] 无法登录，退出")
        return

    if MAKE_ADMIN:
        ensure_admin(email, DB_PATH)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 参数输入
    gzh_name = prompt("输入要搜索的公众号名称", None)
    if not gzh_name:
        print("[ERR] 公众号名称不能为空")
        return
    try:
        max_articles = int(prompt("抓取文章数量(0表示全量)", "0"))
    except Exception:
        max_articles = 0

    # /gzhaccount/search
    print("\n[1/2] 调用 /gzhaccount/search …")
    body = {"name": gzh_name, "max_articles": max_articles}
    r = requests.post(f"{BASE_URL}/gzhaccount/search", headers=headers, json=body, timeout=60)
    if r.status_code != 200:
        print(f"[ERR] /gzhaccount/search 返回 {r.status_code}: {r.text}")
        return
    search_result = r.json()
    out1 = f"gzh_{gzh_name}_search.json"
    with open(out1, "w", encoding="utf-8") as f:
        json.dump(search_result, f, ensure_ascii=False, indent=2)
    print(f"[OK] 搜索结果已保存: {out1}")

    # /gzhaccount/list —— 使用“实际建档名称”（避免搜索名与昵称不一致导致查不到）
    account = (search_result or {}).get("account")
    actual_name = None
    if account and isinstance(account, dict):
        actual_name = account.get("name") or gzh_name
    else:
        actual_name = gzh_name

    try:
        limit = int(prompt("分页limit", "20"))
    except Exception:
        limit = 20
    try:
        offset = int(prompt("分页offset", "0"))
    except Exception:
        offset = 0

    print("\n[2/2] 调用 /gzhaccount/list …")
    print(f"提示：列表查询将使用建档名称：{actual_name}")
    rp = requests.get(
        f"{BASE_URL}/gzhaccount/list",
        headers={"Authorization": f"Bearer {token}"},
        params={"name": actual_name, "offset": offset, "limit": limit},
        timeout=60,
    )
    if rp.status_code != 200:
        print(f"[ERR] /gzhaccount/list 返回 {rp.status_code}: {rp.text}")
        return
    list_result = rp.json()
    out2 = f"gzh_{gzh_name}_list.json"
    with open(out2, "w", encoding="utf-8") as f:
        json.dump(list_result, f, ensure_ascii=False, indent=2)
    print(f"[OK] 列表结果已保存: {out2}")

    # 提示当前 cookie 状态
    print("\n提示：如果 /gzhaccount/search 提示当前没有可用cookie，请先运行 cookie 登录脚本生成并设置为当前。")
    print("例如：python script/cookie_login_test.py，然后 /cookie/change 切换到需要的 cookie。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断。")
