from __future__ import annotations

import os
import time
import json
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from urllib.parse import quote

import requests
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from app.models.cookie import Cookie
from app.models.mp_account import MpAccount
from app.models.mp_article import MpArticle

from app.services.cookie import CookieService


class GzhAccountService:
    def __init__(self, db: Session, static_root: str = os.path.join("static", "mp_accounts")) -> None:
        self.db = db
        self.static_root = static_root
        os.makedirs(self.static_root, exist_ok=True)

    def stream_search(self, *, owner_email: str, name: str, max_articles: int = 0):
        """
        流式搜索：每处理完一页就产出一条进度消息。
        采用 NDJSON（每行一个 JSON 对象）风格，由路由层做 JSON 序列化并通过 StreamingResponse 发送。
        事件结构：
          - {"type": "account", "account": MpAccount}
          - {"type": "page", "page": int, "new_added": int, "total_db": int, "items": List[MpArticle], "has_more": bool}
          - {"type": "done", "total_db": int, "items": List[MpArticle]}
          - {"type": "error", "message": str}
        """
        from sqlalchemy import desc

        try:
            ck = self._get_current_cookie(owner_email)
        except ValueError as e:
            yield {"type": "error", "message": str(e)}
            return

        session = self._requests_session_from_cookie(folder=ck.local, cookie_string=None)
        token = ck.token

        # 1) 搜索账号
        try:
            search_url = f"https://mp.weixin.qq.com/cgi-bin/searchbiz?action=search_biz&token={token}&lang=zh_CN&f=json&ajax=1&random={time.time()}&query={quote(name)}&begin=0&count=5"
            data = session.get(search_url, timeout=30).json()
        except Exception as e:
            yield {"type": "error", "message": f"搜索失败: {e}"}
            return
        if not data or not data.get('list'):
            yield {"type": "error", "message": "未找到公众号"}
            return
        entry = data['list'][0]
        nickname = entry.get('nickname')
        fakeid = entry.get('fakeid')
        avatar_url = entry.get('round_head_img') or ''
        signature = entry.get('signature') or None
        if not nickname or not fakeid:
            yield {"type": "error", "message": "公众号信息不完整"}
            return

        if avatar_url and avatar_url.startswith('http://'):
            avatar_url = avatar_url.replace('http://', 'https://')
        avatar_local = self._download_avatar(nickname, avatar_url) if avatar_url else None

        existed_before = bool(self.db.scalar(select(MpAccount).where(MpAccount.name == nickname)))
        acc = self.db.scalar(select(MpAccount).where(MpAccount.name == nickname))
        if not acc:
            acc = MpAccount(
                name=nickname,
                biz=fakeid,
                description=signature,
                category_id=None,
                owner_email=owner_email,
                avatar_url=avatar_url,
                avatar=avatar_local,
                article_account=0,
            )
            self.db.add(acc)
        else:
            acc.biz = fakeid
            acc.description = signature
            acc.avatar_url = avatar_url
            acc.avatar = avatar_local
            acc.update_time = datetime.now(timezone.utc)
            self.db.add(acc)
        self.db.commit()
        self.db.refresh(acc)

        # 发送账号信息事件
        yield {"type": "account", "account": acc}

        # 工具：获取并返回当前前 n 条
        def current_top_items() -> list[MpArticle]:
            q = select(MpArticle).where(MpArticle.mp_account == nickname).order_by(desc(MpArticle.publish_date), desc(MpArticle.create_time))
            if max_articles and max_articles > 0:
                q = q.limit(max_articles)
            return self.db.scalars(q).all()

        page_no = 0
        if not existed_before:
            # 首次：全量抓取
            begin = 0
            while True:
                page_no += 1
                page, count = self._fetch_articles_page(session=session, token=token, fakeid=fakeid, begin=begin, count=5)
                if not page:
                    break
                new_objs = self._persist_articles(nickname, page)
                # 更新统计
                acc.article_account = self.db.scalar(select(func.count()).where(MpArticle.mp_account == nickname)) or 0
                acc.update_time = datetime.now(timezone.utc)
                self.db.add(acc)
                self.db.commit()
                self.db.refresh(acc)

                items = current_top_items()
                has_more = bool(count and begin + 5 < count)
                yield {
                    "type": "page",
                    "page": page_no,
                    "new_added": len(new_objs),
                    "total_db": acc.article_account,
                    "items": items,
                    "has_more": has_more,
                }
                begin += 5
                if count and begin >= count:
                    break
        else:
            # 增量：遇到第一条已存在即停止
            begin = 0
            stop = False
            while not stop:
                page_no += 1
                page, count = self._fetch_articles_page(session=session, token=token, fakeid=fakeid, begin=begin, count=5)
                if not page:
                    break
                new_objs: list[MpArticle] = []
                for a in page:
                    url = a.get('link') or ''
                    if not url:
                        continue
                    exists = self.db.scalar(select(MpArticle).where(MpArticle.url == url))
                    if exists:
                        stop = True
                        break
                    ist = a.get('item_show_type')
                    ist_int = int(ist) if isinstance(ist, int) else (int(ist) if isinstance(ist, str) and ist.isdigit() else None)
                    obj = MpArticle(
                        title=a.get('title') or '无标题',
                        url=url,
                        cover_url=a.get('cover') or None,
                        publish_date=datetime.fromtimestamp(a.get('update_time') or 0, tz=timezone.utc).isoformat() if a.get('update_time') else None,
                        item_show_type=ist_int,
                        mp_account=nickname,
                    )
                    self.db.add(obj)
                    new_objs.append(obj)
                if new_objs:
                    self.db.commit()
                    for o in new_objs:
                        self.db.refresh(o)
                # 更新统计
                acc.article_account = self.db.scalar(select(func.count()).where(MpArticle.mp_account == nickname)) or 0
                acc.update_time = datetime.now(timezone.utc)
                self.db.add(acc)
                self.db.commit()
                self.db.refresh(acc)

                items = current_top_items()
                has_more = not stop and bool(count and begin + 5 < count)
                yield {
                    "type": "page",
                    "page": page_no,
                    "new_added": len(new_objs),
                    "total_db": acc.article_account,
                    "items": items,
                    "has_more": has_more,
                }
                if stop:
                    break
                begin += 5
                if count and begin >= count:
                    break

        # 完成事件
        final_items = current_top_items()
        yield {"type": "done", "total_db": len(final_items) if (max_articles and max_articles > 0) else acc.article_account, "items": final_items, "account": acc}

    def _get_current_cookie(self, owner_email: str) -> Cookie:
        stmt = select(Cookie).where(and_(Cookie.owner_email == owner_email, Cookie.is_current == True))
        ck = self.db.scalar(stmt)
        if not ck:
            raise ValueError("当前没有可用的cookie，请先登录并设置当前cookie")
        # 过期检查
        from datetime import datetime, timezone
        if ck.expire_time <= datetime.now(timezone.utc):
            raise ValueError("当前cookie已过期，请重新登录")
        return ck

    def _requests_session_from_cookie(self, folder: str, cookie_string: Optional[str] = None) -> requests.Session:
        import pickle
        s = requests.Session()
        # headers 基础设置
        s.headers.update({
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'referer': 'https://mp.weixin.qq.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest'
        })
        # 载入 cookies
        cookie_path = os.path.join(folder, 'gzhcookies.cookie')
        if os.path.exists(cookie_path):
            try:
                with open(cookie_path, 'rb') as f:
                    s.cookies = pickle.load(f)
            except Exception:
                pass
        if cookie_string:
            s.headers['Cookie'] = cookie_string
        return s

    def _download_avatar(self, name: str, avatar_url: str) -> str:
        safe_name = ''.join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        folder = os.path.join(self.static_root, safe_name)
        os.makedirs(folder, exist_ok=True)
        import urllib.parse
        ext = '.jpg'
        try:
            path = urllib.parse.urlparse(avatar_url).path
            _, e = os.path.splitext(path)
            if e:
                ext = e
        except Exception:
            pass
        local = os.path.join(folder, f"avatar{ext}")
        try:
            r = requests.get(avatar_url, timeout=10)
            if r.status_code == 200:
                with open(local, 'wb') as f:
                    f.write(r.content)
        except Exception:
            pass
        return local

    # ------------------- Search account -------------------
    def search_account(self, *, owner_email: str, name: str, max_articles: int = 0) -> tuple[Optional[MpAccount], list[MpArticle]]:
        """
        新逻辑：
        1) 首次搜索（库中无该账号）：先全量抓取并入库，再返回按发布时间倒序的前 n 条（n<=0 表示全量返回）。
        2) 再次搜索（库中已有该账号）：进行增量抓取，从第 1 页开始按时间从新到旧遍历；
           在同一页内遇到第一条“已存在”的文章即停止继续翻页（认为已到达重叠边界），
           将本页之前的新文章入库；然后返回按发布时间倒序的前 n 条（n<=0 表示全量返回）。
        返回的 articles 为“当前库中的前 n 条”，不再仅限于“本次新增”。
        """
        from sqlalchemy import desc

        ck = self._get_current_cookie(owner_email)
        session = self._requests_session_from_cookie(folder=ck.local, cookie_string=None)
        token = ck.token

        # 1) 搜索账号
        search_url = f"https://mp.weixin.qq.com/cgi-bin/searchbiz?action=search_biz&token={token}&lang=zh_CN&f=json&ajax=1&random={time.time()}&query={quote(name)}&begin=0&count=5"
        data = session.get(search_url, timeout=30).json()
        if not data or not data.get('list'):
            return None, []
        entry = data['list'][0]
        nickname = entry.get('nickname')
        fakeid = entry.get('fakeid')
        avatar_url = entry.get('round_head_img') or ''
        signature = entry.get('signature') or None
        if not nickname or not fakeid:
            return None, []

        # 下载头像
        if avatar_url and avatar_url.startswith('http://'):
            avatar_url = avatar_url.replace('http://', 'https://')
        avatar_local = self._download_avatar(nickname, avatar_url) if avatar_url else None

        # 记录是否为首次（库中是否已有该账号）
        existed_before = bool(self.db.scalar(select(MpAccount).where(MpAccount.name == nickname)))

        # Upsert mp_accounts
        acc = self.db.scalar(select(MpAccount).where(MpAccount.name == nickname))
        if not acc:
            acc = MpAccount(
                name=nickname,
                biz=fakeid,
                description=signature,
                category_id=None,
                owner_email=owner_email,
                avatar_url=avatar_url,
                avatar=avatar_local,
                article_account=0,
            )
            self.db.add(acc)
        else:
            acc.biz = fakeid
            acc.description = signature
            acc.avatar_url = avatar_url
            acc.avatar = avatar_local
            acc.update_time = datetime.now(timezone.utc)
            self.db.add(acc)
        self.db.commit()
        self.db.refresh(acc)

        # 2) 抓取文章
        if not existed_before:
            # 首次：全量抓取
            begin = 0
            while True:
                page, count = self._fetch_articles_page(session=session, token=token, fakeid=fakeid, begin=begin, count=5)
                if not page:
                    break
                _ = self._persist_articles(nickname, page)
                begin += 5
                if count and begin >= count:
                    break
        else:
            # 存在：增量抓取，遇到第一条已存在即停止
            begin = 0
            stop = False
            while not stop:
                page, count = self._fetch_articles_page(session=session, token=token, fakeid=fakeid, begin=begin, count=5)
                if not page:
                    break
                new_objs: list[MpArticle] = []
                for a in page:
                    url = a.get('link') or ''
                    if not url:
                        continue
                    exists = self.db.scalar(select(MpArticle).where(MpArticle.url == url))
                    if exists:
                        stop = True
                        break
                    # 未存在则入内存，稍后批量提交
                    ist = a.get('item_show_type')
                    ist_int = int(ist) if isinstance(ist, int) else (int(ist) if isinstance(ist, str) and ist.isdigit() else None)
                    obj = MpArticle(
                        title=a.get('title') or '无标题',
                        url=url,
                        cover_url=a.get('cover') or None,
                        publish_date=datetime.fromtimestamp(a.get('update_time') or 0, tz=timezone.utc).isoformat() if a.get('update_time') else None,
                        item_show_type=ist_int,
                        mp_account=nickname,
                    )
                    self.db.add(obj)
                    new_objs.append(obj)
                if new_objs:
                    self.db.commit()
                    for o in new_objs:
                        self.db.refresh(o)
                if stop:
                    break
                begin += 5
                if count and begin >= count:
                    break

        # 3) 更新统计
        acc.article_account = self.db.scalar(select(func.count()).where(MpArticle.mp_account == nickname)) or 0
        acc.update_time = datetime.now(timezone.utc)
        self.db.add(acc)
        self.db.commit()
        self.db.refresh(acc)

        # 4) 返回：按发布时间从近到远取前 n 条（n<=0 表示全量）
        q = select(MpArticle).where(MpArticle.mp_account == nickname).order_by(desc(MpArticle.publish_date), desc(MpArticle.create_time))
        if max_articles and max_articles > 0:
            q = q.limit(max_articles)
        top_items = self.db.scalars(q).all()
        return acc, top_items

    def _fetch_articles_page(self, *, session: requests.Session, token: str, fakeid: str, begin: int, count: int) -> tuple[list[dict], int | None]:
        url = f"https://mp.weixin.qq.com/cgi-bin/appmsgpublish?sub=list&search_field=null&begin={begin}&count={count}&query=&fakeid={fakeid}&type=101_1&free_publish_type=1&sub_action=list_ex&fingerprint={int(time.time())}&token={token}&lang=zh_CN&f=json&ajax=1"
        try:
            r = session.get(url, timeout=30)
            data = r.json()
            publish_page = json.loads(data.get('publish_page', '{}'))
            total_count = publish_page.get('total_count')
            out: list[dict] = []
            for item in publish_page.get('publish_list', []):
                try:
                    pub = json.loads(item.get('publish_info', '{}'))
                except Exception:
                    pub = {}
                for art in pub.get('appmsgex', []) or []:
                    # 注意：item_show_type 可能为 0（有效值），不能用 "or" 回退
                    item_show_type_raw = art.get('item_show_type')
                    out.append({
                        'title': art.get('title') or '无标题',
                        'cover': art.get('cover') or '',
                        'link': art.get('link') or '',
                        'update_time': art.get('update_time') or 0,
                        'item_show_type': item_show_type_raw if item_show_type_raw is not None else None,
                    })
            return out, total_count
        except Exception:
            return [], None

    def _persist_articles(self, account_name: str, items: list[dict]) -> list[MpArticle]:
        new_objs: list[MpArticle] = []
        for a in items:
            url = a.get('link') or ''
            if not url:
                continue
            exists = self.db.scalar(select(MpArticle).where(MpArticle.url == url))
            if exists:
                continue
            ist = a.get('item_show_type')
            # 0/8/11 等有效整数，不要用 or 造成 0 被当空值
            ist_int = int(ist) if isinstance(ist, (int,)) else (int(ist) if isinstance(ist, str) and ist.isdigit() else None)
            obj = MpArticle(
                title=a.get('title') or '无标题',
                url=url,
                cover_url=a.get('cover') or None,
                publish_date=datetime.fromtimestamp(a.get('update_time') or 0, tz=timezone.utc).isoformat() if a.get('update_time') else None,
                item_show_type=ist_int,
                mp_account=account_name,
            )
            self.db.add(obj)
            new_objs.append(obj)
        if new_objs:
            self.db.commit()
            for o in new_objs:
                self.db.refresh(o)
        return new_objs

    # ------------------- List articles -------------------
    def list_articles(self, *, owner_email: str, name: str, offset: int, limit: int) -> tuple[list[MpArticle], int]:
        # 若增量策略：先尝试从远端拉取最新一页，若发现已有，则直接从DB读取
        acc = self.db.scalar(select(MpAccount).where(MpAccount.name == name))
        if not acc:
            raise ValueError("先执行 /gzhaccount/search 完成账号建档，再获取文章列表")
        # 简化：仅从DB分页
        from sqlalchemy import desc
        stmt = select(MpArticle).where(MpArticle.mp_account == name).order_by(desc(MpArticle.create_time)).offset(offset).limit(limit)
        items = self.db.scalars(stmt).all()
        total = self.db.scalar(select(func.count()).where(MpArticle.mp_account == name)) or 0
        return items, int(total)
