from __future__ import annotations

import base64
import json
import os
import pickle
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

import requests
from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from app.models.cookie import Cookie as CookieModel

# 全局内存存储（仅单进程测试环境）：login_key -> 会话状态
IMMEDIATE_STORE: dict[str, dict] = {}
IMMEDIATE_TTL_SECONDS = 300  # 5分钟超时


DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass
class WechatLoginResult:
    status: str  # success | pending | failed
    message: str
    qrcode_base64: Optional[str] = None
    token: Optional[str] = None
    cookie_string: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    avatar_local: Optional[str] = None
    folder_local: Optional[str] = None
    login_key: Optional[str] = None


class CookieService:
    def __init__(self, db: Session, static_root: str = os.path.join("static", "cookies")) -> None:
        self.db = db
        self.static_root = static_root
        os.makedirs(self.static_root, exist_ok=True)
        # 使用全局 IMMEDIATE_STORE，避免每次实例化覆盖存量（仅单进程测试环境）
        # 多实例或多进程部署请改用 Redis/数据库来存储会话状态
        # 这里不再在实例上维护 _immediate_store

    # ------------------ Public DB operations ------------------
    def set_current_cookie(self, owner_email: str, token: str) -> CookieModel:
        obj = self.db.scalar(
            select(CookieModel).where(
                and_(CookieModel.owner_email == owner_email, CookieModel.token == token)
            )
        )
        if not obj:
            raise ValueError("Cookie not found for this user")
        # Unset others
        self.db.execute(
            update(CookieModel)
            .where(and_(CookieModel.owner_email == owner_email, CookieModel.token != token))
            .values(is_current=False)
        )
        obj.is_current = True
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def list_valid_cookies(self, owner_email: str) -> list[CookieModel]:
        self.cleanup_expired(owner_email)
        now = datetime.now(timezone.utc)
        stmt = (
            select(CookieModel)
            .where(and_(CookieModel.owner_email == owner_email, CookieModel.expire_time > now))
            .order_by(CookieModel.created_time.desc())
        )
        return self.db.scalars(stmt).all()

    def delete_cookie(self, owner_email: str, token: str) -> None:
        obj = self.db.scalar(
            select(CookieModel).where(
                and_(CookieModel.owner_email == owner_email, CookieModel.token == token)
            )
        )
        if not obj:
            raise ValueError("Cookie not found for this user")
        # remove folder
        try:
            if obj.local and os.path.isdir(obj.local):
                import shutil
                shutil.rmtree(obj.local, ignore_errors=True)
        except Exception:
            pass
        self.db.delete(obj)
        self.db.commit()

    def cleanup_expired(self, owner_email: Optional[str] = None) -> int:
        now = datetime.now(timezone.utc)
        if owner_email:
            stmt = select(CookieModel).where(
                and_(CookieModel.owner_email == owner_email, CookieModel.expire_time <= now)
            )
        else:
            stmt = select(CookieModel).where(CookieModel.expire_time <= now)
        expired = self.db.scalars(stmt).all()
        count = 0
        for obj in expired:
            try:
                if obj.local and os.path.isdir(obj.local):
                    import shutil
                    shutil.rmtree(obj.local, ignore_errors=True)
            except Exception:
                pass
            self.db.delete(obj)
            count += 1
        if count:
            self.db.commit()
        return count

    # ------------------ WeChat Login Flow ------------------
    def wechat_login(self, *, timeout_seconds: int = 180) -> WechatLoginResult:
        """
        兼容的阻塞式扫码模式（保留）。
        """
        return self._wechat_login_blocking(timeout_seconds=timeout_seconds)

    def wechat_login_immediate_start(self) -> WechatLoginResult:
        """开始登录：立即返回二维码与 login_key，不阻塞轮询。"""
        import secrets
        session = requests.session()
        headers = {
            "User-Agent": DEFAULT_UA,
            "Referer": "https://mp.weixin.qq.com/",
            "Host": "mp.weixin.qq.com",
        }
        try:
            session.get("https://mp.weixin.qq.com/", headers=headers, timeout=10)
            session.post(
                "https://mp.weixin.qq.com/cgi-bin/bizlogin?action=startlogin",
                data=(
                    "userlang=zh_CN&redirect_url=&login_type=3&sessionid={}&token=&lang=zh_CN&f=json&ajax=1".format(
                        int(time.time() * 1000)
                    )
                ),
                headers=headers,
                timeout=10,
            )
            qr_resp = session.get(
                "https://mp.weixin.qq.com/cgi-bin/scanloginqrcode?action=getqrcode&random={}".format(
                    int(time.time() * 1000)
                ),
                timeout=10,
            )
            qr_b64 = base64.b64encode(qr_resp.content).decode("ascii")

            login_key = secrets.token_urlsafe(24)
            IMMEDIATE_STORE[login_key] = {
                "session": session,
                "headers": headers,
                "qr_b64": qr_b64,
                "status": "pending",
                "created": time.time(),
            }
            return WechatLoginResult(status="pending", message="二维码已生成，请扫码", qrcode_base64=qr_b64, login_key=login_key)
        except Exception as e:
            return WechatLoginResult(status="failed", message=f"初始化登录失败: {e}")

    def wechat_login_immediate_poll(self, *, login_key: str) -> WechatLoginResult:
        """轮询扫码状态：成功则完成保存 cookie.json 与文件。"""
        # 清理过期 login_key
        now = time.time()
        for k, v in list(IMMEDIATE_STORE.items()):
            if now - v.get("created", 0) > IMMEDIATE_TTL_SECONDS:
                try:
                    del IMMEDIATE_STORE[k]
                except Exception:
                    pass
        st = IMMEDIATE_STORE.get(login_key)
        if not st:
            return WechatLoginResult(status="failed", message="login_key 无效或已过期")
        session: requests.Session = st["session"]
        headers = st["headers"]
        qr_b64 = st["qr_b64"]
        try:
            data = session.get(
                "https://mp.weixin.qq.com/cgi-bin/scanloginqrcode?action=ask&token=&lang=zh_CN&f=json&ajax=1",
                timeout=10,
            ).json()
            status = data.get("status")
            if status == 0:
                return WechatLoginResult(status="pending", message="二维码未失效，请扫码", qrcode_base64=qr_b64)
            if status == 6:
                return WechatLoginResult(status="pending", message="已扫码，请在手机确认", qrcode_base64=qr_b64)
            if status == 1:
                # 确认登录
                login_data = session.post(
                    "https://mp.weixin.qq.com/cgi-bin/bizlogin?action=login",
                    data=(
                        "userlang=zh_CN&redirect_url=&cookie_forbidden=0&cookie_cleaned=1&plugin_used=0&login_type=3&token=&lang=zh_CN&f=json&ajax=1"
                    ),
                    headers=headers,
                    timeout=10,
                ).json()
                redirect_url = login_data.get("redirect_url")
                if not redirect_url:
                    return WechatLoginResult(status="failed", message="登录失败：未返回redirect_url", qrcode_base64=qr_b64)
                token = parse_qs(urlparse(redirect_url).query).get("token", [None])[0]
                session.get(f"https://mp.weixin.qq.com{redirect_url}", headers=headers, timeout=10)
                cookie_string = "; ".join([f"{n}={v}" for n, v in session.cookies.items()])

                folder = os.path.join(self.static_root, token)
                os.makedirs(folder, exist_ok=True)
                with open(os.path.join(folder, "gzhcookies.cookie"), "wb") as f:
                    pickle.dump(session.cookies, f)
                name, avatar_url, avatar_local = self._fetch_account_info(session, headers, token, folder, cookie_string)
                now_epoch = int(time.time())
                info = {
                    "token": token,
                    "cookie": cookie_string,
                    "created_time": now_epoch,
                    "expire_time": now_epoch + 88 * 3600,
                    "request_count": 0,
                    "request_reset_time": now_epoch + 3600,
                    "request_history": [],
                    "name": name,
                    "avatar": avatar_local,
                    "avatar_url": avatar_url,
                }
                with open(os.path.join(folder, "cookie.json"), "w", encoding="utf-8") as f:
                    json.dump(info, f, ensure_ascii=False, indent=2)

                # 完成后删除会话
                try:
                    del IMMEDIATE_STORE[login_key]
                except Exception:
                    pass

                return WechatLoginResult(
                    status="success",
                    message="登录成功",
                    qrcode_base64=qr_b64,
                    token=token,
                    cookie_string=cookie_string,
                    name=name,
                    avatar_url=avatar_url,
                    avatar_local=avatar_local,
                    folder_local=folder,
                )
            return WechatLoginResult(status="pending", message="等待扫码/确认", qrcode_base64=qr_b64)
        except Exception as e:
            return WechatLoginResult(status="failed", message=f"轮询失败: {e}")

    def _wechat_login_blocking(self, *, timeout_seconds: int) -> WechatLoginResult:
        session = requests.session()
        headers = {
            "User-Agent": DEFAULT_UA,
            "Referer": "https://mp.weixin.qq.com/",
            "Host": "mp.weixin.qq.com",
        }
        try:
            session.get("https://mp.weixin.qq.com/", headers=headers, timeout=10)
            session.post(
                "https://mp.weixin.qq.com/cgi-bin/bizlogin?action=startlogin",
                data=(
                    "userlang=zh_CN&redirect_url=&login_type=3&sessionid={}&token=&lang=zh_CN&f=json&ajax=1".format(
                        int(time.time() * 1000)
                    )
                ),
                headers=headers,
                timeout=10,
            )
            qr_resp = session.get(
                "https://mp.weixin.qq.com/cgi-bin/scanloginqrcode?action=getqrcode&random={}".format(
                    int(time.time() * 1000)
                ),
                timeout=10,
            )
            qr_bytes = qr_resp.content
            qr_b64 = base64.b64encode(qr_bytes).decode("ascii")

            ask_url = (
                "https://mp.weixin.qq.com/cgi-bin/scanloginqrcode?action=ask&token=&lang=zh_CN&f=json&ajax=1"
            )
            deadline = time.time() + timeout_seconds
            last_status_msg = "二维码已生成，请扫码"

            while time.time() < deadline:
                try:
                    data = session.get(ask_url, timeout=10).json()
                except Exception:
                    time.sleep(2)
                    continue
                status = data.get("status")
                if status == 0:
                    last_status_msg = "二维码未失效，请扫码"
                elif status == 6:
                    last_status_msg = "已扫码，请在手机确认"
                elif status == 1:
                    # Confirmed
                    login_data = session.post(
                        "https://mp.weixin.qq.com/cgi-bin/bizlogin?action=login",
                        data=(
                            "userlang=zh_CN&redirect_url=&cookie_forbidden=0&cookie_cleaned=1&plugin_used=0&login_type=3&token=&lang=zh_CN&f=json&ajax=1"
                        ),
                        headers=headers,
                        timeout=10,
                    ).json()
                    redirect_url = login_data.get("redirect_url")
                    if not redirect_url:
                        return WechatLoginResult(status="failed", message="登录失败：未返回redirect_url", qrcode_base64=qr_b64)
                    token = parse_qs(urlparse(redirect_url).query).get("token", [None])[0]
                    # visit redirect to set cookies fully
                    session.get(f"https://mp.weixin.qq.com{redirect_url}", headers=headers, timeout=10)
                    cookie_string = "; ".join([f"{n}={v}" for n, v in session.cookies.items()])

                    # build folder
                    folder = os.path.join(self.static_root, token)
                    os.makedirs(folder, exist_ok=True)
                    # save cookies pickle file
                    with open(os.path.join(folder, "gzhcookies.cookie"), "wb") as f:
                        pickle.dump(session.cookies, f)

                    # fetch account info (name, avatar)
                    name, avatar_url, avatar_local = self._fetch_account_info(session, headers, token, folder, cookie_string)

                    # build cookie.json
                    now_epoch = int(time.time())
                    info = {
                        "token": token,
                        "cookie": cookie_string,
                        "created_time": now_epoch,
                        "expire_time": now_epoch + 88 * 3600,
                        "request_count": 0,
                        "request_reset_time": now_epoch + 3600,
                        "request_history": [],
                        "name": name,
                        "avatar": avatar_local,
                        "avatar_url": avatar_url,
                    }
                    with open(os.path.join(folder, "cookie.json"), "w", encoding="utf-8") as f:
                        json.dump(info, f, ensure_ascii=False, indent=2)

                    return WechatLoginResult(
                        status="success",
                        message="登录成功",
                        qrcode_base64=qr_b64,
                        token=token,
                        cookie_string=cookie_string,
                        name=name,
                        avatar_url=avatar_url,
                        avatar_local=avatar_local,
                        folder_local=folder,
                    )
                time.sleep(3)

            return WechatLoginResult(status="pending", message=last_status_msg, qrcode_base64=qr_b64)
        except Exception as e:
            return WechatLoginResult(status="failed", message=f"登录异常: {e}")

    def persist_login_for_user(self, *, owner_email: str, result: WechatLoginResult) -> CookieModel:
        if result.status != "success" or not result.token:
            raise ValueError("登录未成功，无法保存")
        created = datetime.now(timezone.utc)
        expire = created + timedelta(hours=88)
        # unset current others
        self.db.execute(
            update(CookieModel)
            .where(CookieModel.owner_email == owner_email)
            .values(is_current=False)
        )
        obj = CookieModel(
            token=result.token,
            owner_email=owner_email,
            created_time=created,
            expire_time=expire,
            name=result.name or "",
            avatar_url=result.avatar_url or None,
            avatar=result.avatar_local or None,
            local=result.folder_local or "",
            is_current=True,
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    # ------------------ Helpers ------------------
    def _fetch_account_info(
        self, session: requests.Session, headers: dict, token: str, folder: str, cookie_string: Optional[str] = None
    ) -> Tuple[str, str, str]:
        """Return (name, avatar_url, avatar_local).
        更加鲁棒：同时匹配单/双引号与多个页面。"""
        def _normalize(u: str) -> str:
            if not u:
                return u
            if u.startswith("//"):
                return "https:" + u
            if u.startswith("http://"):
                return u.replace("http://", "https://")
            return u

        try:
            # 1) 主页获取（带上 Cookie 头）
            hdrs = {
                "User-Agent": headers.get("User-Agent", DEFAULT_UA),
                "Referer": headers.get("Referer", "https://mp.weixin.qq.com/"),
                "Host": "mp.weixin.qq.com",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            if cookie_string:
                hdrs["Cookie"] = cookie_string
            else:
                # 回退：将 session cookies 拼成 Cookie 头
                try:
                    ck = "; ".join([f"{n}={v}" for n, v in session.cookies.items()])
                    if ck:
                        hdrs["Cookie"] = ck
                except Exception:
                    pass

            resp = session.get(
                f"https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=zh_CN&token={token}",
                headers=hdrs,
                timeout=15,
            )
            if resp.status_code == 200:
                content = resp.text
                # 优先解析 window.wx.commonData
                m = re.search(r"window\\.wx\\.commonData\\s*=\\s*({[\\s\\S]*?});", content)
                if m:
                    js = m.group(1)
                    nn = re.search(r"nick_name\s*:\s*['\"]([^'\"]+)['\"]", js)
                    name = nn.group(1) if nn else "公众号"
                    himg = re.search(r"head_img\s*:\s*['\"]([^'\"]+)['\"]", js)
                    avatar_url = _normalize(himg.group(1)) if himg else ""
                    avatar_local = self._download_avatar(avatar_url, folder) if avatar_url else ""
                    return name, avatar_url, avatar_local
                # 备用：在整页中直接找字段
                nn2 = re.search(r"nick[_ ]?name\s*[:=]\s*['\"]([^'\"]+)['\"]", content)
                himg2 = re.search(r"head[_ ]?img\s*[:=]\s*['\"]([^'\"]+)['\"]", content)
                if nn2 or himg2:
                    name = nn2.group(1) if nn2 else "公众号"
                    avatar_url = _normalize(himg2.group(1)) if himg2 else ""
                    avatar_local = self._download_avatar(avatar_url, folder) if avatar_url else ""
                    return name, avatar_url, avatar_local

            # 2) 账号详情页：action=show
            resp2 = session.get(
                f"https://mp.weixin.qq.com/cgi-bin/account?action=show&t=wxm-account&token={token}&lang=zh_CN",
                headers=hdrs,
                timeout=15,
            )
            if resp2.status_code == 200:
                html = resp2.text
                nn3 = re.search(r"var\s+nickname\s*=\s*['\"]([^'\"]+)['\"]", html)
                himg3 = re.search(r"var\s+headimg\s*=\s*['\"]([^'\"]+)['\"]", html)
                if nn3 or himg3:
                    name = nn3.group(1) if nn3 else "公众号"
                    avatar_url = _normalize(himg3.group(1)) if himg3 else ""
                    avatar_local = self._download_avatar(avatar_url, folder) if avatar_url else ""
                    return name, avatar_url, avatar_local
        except Exception:
            pass
        return "公众号", "", ""

    def _download_avatar(self, avatar_url: str, folder: str) -> str:
        if not avatar_url:
            return ""
        try:
            r = requests.get(avatar_url, timeout=10)
            if r.status_code == 200:
                path = os.path.join(folder, "avatar.jpg")
                with open(path, "wb") as f:
                    f.write(r.content)
                return path
        except Exception:
            pass
        return ""
