#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web版微信公众号搜索器
去掉人工交互，添加自动延时，支持Web接口调用
"""

import time
import random
import requests
import os
import json
import hashlib
from datetime import datetime
from urllib.parse import quote
from threading import Thread
import logging
from urllib.parse import urlparse

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WebWeChatSearcher:
    """
    Web版搜索器 - 去掉人工交互，支持异步搜索
    """
    
    def __init__(self, gzh_name, token=None, max_articles=0):
        self.gzh_name = gzh_name
        self.token = token
        self.max_articles = max_articles  # 0表示搜索全部
        self.searching = True
        self.total_articles_fetched = 0
        self.session = requests.Session()
        self.articles_data = []
        self.search_status = "初始化中"
        self.search_progress = 0
        self.gzh_info = None
        
        # 生成32位fingerprint
        self.fingerprint = self._generate_fingerprint()
        
        try:
            self.login_info = self._load_cookie(token)
            self._setup_session()
            logger.info(f"生成的32位Fingerprint: {self.fingerprint}")
            self.search_status = "初始化完成"
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            self.searching = False
            self.search_status = f"初始化失败: {e}"

    def _generate_fingerprint(self):
        """生成32位fingerprint"""
        timestamp = int(time.time() * 1000)
        random_part = random.randint(100000, 999999)
        combined = f"fingerprint_{timestamp}_{random_part}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()

    def _load_cookie(self, token=None):
        """加载Cookie"""
        cookies_dir = 'cookies'
        
        if token:
            # 根据token查找对应的cookie文件
            for sub_dir in os.listdir(cookies_dir):
                sub_dir_path = os.path.join(cookies_dir, sub_dir)
                if os.path.isdir(sub_dir_path):
                    cookie_file_path = os.path.join(sub_dir_path, 'cookie.json')
                    if os.path.exists(cookie_file_path):
                        with open(cookie_file_path, 'r', encoding='utf-8') as f:
                            login_info = json.load(f)
                            if login_info.get('token') == token:
                                logger.info(f"加载Cookie账号: {os.path.basename(sub_dir_path)}")
                                return login_info
            raise Exception(f"未找到token对应的cookie文件: {token}")
        else:
            # 使用第一个可用的cookie
            sub_dirs = [d for d in os.listdir(cookies_dir) if os.path.isdir(os.path.join(cookies_dir, d))]
            if not sub_dirs:
                raise Exception("未找到任何cookie文件")
            
            account_dir = os.path.join(cookies_dir, sub_dirs[0])
            cookie_file_path = os.path.join(account_dir, 'cookie.json')

            with open(cookie_file_path, 'r', encoding='utf-8') as f:
                login_info = json.load(f)
                
            logger.info(f"加载Cookie账号: {os.path.basename(account_dir)}")
            return login_info

    def _setup_session(self):
        """设置会话"""
        self.session.headers.update({
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,ja;q=0.6',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'cookie': self.login_info['cookie'],
            'priority': 'u=1, i',
            'referer': f'https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2&action=edit&isNew=1&type=77&createType=0&token={self.login_info["token"]}&lang=zh_CN&timestamp=1756885829443',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest'
        })

    def _make_request(self, url):
        """发送请求"""
        try:
            # 随机延时1-3秒，避免请求过于频繁
            delay = random.uniform(1.0, 3.0)
            time.sleep(delay)
            
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'base_resp' in data:
                        ret_code = data['base_resp'].get('ret', 0)
                        if ret_code == 0:
                            return data
                        elif ret_code == 200013:
                            logger.warning("遇到200013错误，重新生成fingerprint")
                            self.fingerprint = self._generate_fingerprint()
                            logger.info(f"新fingerprint: {self.fingerprint}")
                            return None
                        else:
                            logger.error(f"API错误: {ret_code}")
                            return None
                    else:
                        return data
                except json.JSONDecodeError:
                    logger.error("JSON解析失败")
                    return None
            else:
                logger.error(f"HTTP错误: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"请求异常: {e}")
            return None

    def search_gzh(self, gzh_name):
        """搜索公众号"""
        encoded_name = quote(gzh_name)
        search_url = f'https://mp.weixin.qq.com/cgi-bin/searchbiz?action=search_biz&token={self.login_info["token"]}&lang=zh_CN&f=json&ajax=1&random={time.time()}&query={encoded_name}&begin=0&count=5&fingerprint={self.fingerprint}'
        
        data = self._make_request(search_url)
        if not data or not data.get('list'):
            return None

        gzh_data = data['list'][0]
        
        # 下载头像到本地
        local_avatar_path = self._download_avatar(gzh_data['nickname'], gzh_data['round_head_img'])
        
        return {
            'name': gzh_data['nickname'],
            'fakeid': gzh_data['fakeid'],
            'avatar_url': gzh_data['round_head_img'],
            'local_avatar_path': local_avatar_path,
            'signature': gzh_data['signature']
        }

    def _download_avatar(self, gzh_name, avatar_url):
        """下载公众号头像到本地"""
        try:
            # 创建公众号专用目录
            safe_gzh_name = "".join(c for c in gzh_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            mp_dir = os.path.join('static', 'mp_accounts', safe_gzh_name)
            os.makedirs(mp_dir, exist_ok=True)
            
            # 获取文件扩展名
            parsed_url = urlparse(avatar_url)
            file_ext = '.jpg'  # 默认jpg格式
            if '.' in parsed_url.path:
                file_ext = os.path.splitext(parsed_url.path)[1]
                if not file_ext:
                    file_ext = '.jpg'
            
            avatar_filename = f"avatar{file_ext}"
            local_path = os.path.join(mp_dir, avatar_filename)
            
            # 如果文件已存在，直接返回路径
            if os.path.exists(local_path):
                logger.info(f"头像已存在: {local_path}")
                return f"/static/mp_accounts/{safe_gzh_name}/{avatar_filename}"
            
            # 下载头像
            logger.info(f"正在下载头像: {avatar_url}")
            response = requests.get(avatar_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://mp.weixin.qq.com/',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            })
            
            if response.status_code == 200:
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"头像下载成功: {local_path}")
                return f"/static/mp_accounts/{safe_gzh_name}/{avatar_filename}"
            else:
                logger.error(f"头像下载失败，状态码: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"下载头像失败: {e}")
            return None

    def _get_content_type(self, item_show_type):
        """根据item_show_type解析内容类型"""
        # 统一转换为整数进行比较
        try:
            item_type = int(item_show_type) if item_show_type is not None else 0
        except (ValueError, TypeError):
            item_type = 0
            
        if item_type == 0:
            return "文章"
        elif item_type == 8:
            return "图文"
        else:
            return f"其他类型({item_type})"

    def get_articles(self, fakeid, begin=0, count=5):
        """获取文章列表"""
        new_url = f'https://mp.weixin.qq.com/cgi-bin/appmsgpublish?sub=list&search_field=null&begin={begin}&count={count}&query=&fakeid={fakeid}&type=101_1&free_publish_type=1&sub_action=list_ex&fingerprint={self.fingerprint}&token={self.login_info["token"]}&lang=zh_CN&f=json&ajax=1'
        
        data = self._make_request(new_url)
        if data:
            return data, 'new'
        
        return None, None

    def _process_page_data(self, data, api_type, page_num):
        """处理页面数据"""
        page_articles = []
        
        try:
            if api_type == 'new' and 'publish_page' in data:
                try:
                    publish_page_data = json.loads(data['publish_page'])
                    
                    total_count = publish_page_data.get('total_count', 0)
                    publish_count = publish_page_data.get('publish_count', 0)
                    masssend_count = publish_page_data.get('masssend_count', 0)
                    
                    logger.info(f"统计信息 - 总文章数: {total_count}, 发表总数: {publish_count}, 群发总数: {masssend_count}")
                    
                    if 'publish_list' in publish_page_data:
                        for item in publish_page_data['publish_list']:
                            if isinstance(item, dict) and 'publish_info' in item:
                                try:
                                    publish_info = json.loads(item['publish_info'])
                                    if 'appmsgex' in publish_info and publish_info['appmsgex']:
                                        for article in publish_info['appmsgex']:
                                            # 解析内容类型
                                            item_show_type = article.get('item_show_type', 0)
                                            content_type = self._get_content_type(item_show_type)
                                            
                                            article_data = {
                                                'title': article.get('title', '无标题'),
                                                'cover': article.get('cover', ''),
                                                'content_url': article.get('link', ''),
                                                'update_time': article.get('update_time', 0),
                                                'itemidx': article.get('itemidx', 0),
                                                'author': article.get('author_name', ''),
                                                'digest': article.get('digest', ''),
                                                'publish_time': datetime.fromtimestamp(article.get('update_time', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                                                'publish_type': item.get('publish_type', 0),
                                                'item_show_type': item_show_type,
                                                'content_type': content_type
                                            }
                                            page_articles.append(article_data)
                                except json.JSONDecodeError:
                                    logger.warning("解析文章信息失败")
                                    continue
                
                except json.JSONDecodeError as e:
                    logger.error(f"解析publish_page失败: {e}")
            
            if not page_articles:
                logger.warning(f"第{page_num}页未找到文章数据")
        
        except Exception as e:
            logger.error(f"处理第{page_num}页数据失败: {e}")
        
        return page_articles

    def get_search_status(self):
        """获取搜索状态"""
        return {
            'status': self.search_status,
            'progress': self.search_progress,
            'total_articles': self.total_articles_fetched,
            'gzh_info': self.gzh_info,
            'articles': self.articles_data[-10:] if self.articles_data else []  # 返回最新的10篇文章
        }

    def load_existing_articles(self):
        """加载已存在的文章数据"""
        safe_gzh_name = "".join(c for c in self.gzh_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        json_filename = os.path.join('static', 'mp_accounts', safe_gzh_name, f"{safe_gzh_name}.json")
        
        existing_data = self._load_existing_data(json_filename)
        if existing_data:
            self.articles_data = existing_data.get('articles', [])
            self.total_articles_fetched = len(self.articles_data)
            self.gzh_info = existing_data.get('gzh_info', self.gzh_info)
            logger.info(f"已加载 {self.total_articles_fetched} 篇已存在文章")
            return True
        return False

    def search_all_articles_async(self, callback=None):
        """异步搜索所有文章"""
        def _search():
            try:
                self.search_status = "搜索公众号中"
                logger.info(f"搜索公众号: {self.gzh_name}")
                
                gzh_info = self.search_gzh(self.gzh_name)
                if not gzh_info:
                    self.search_status = f"未找到公众号: {self.gzh_name}"
                    logger.error(self.search_status)
                    return
                
                self.gzh_info = gzh_info
                self.search_status = f"找到公众号: {gzh_info['name']}"
                logger.info(f"找到公众号: {gzh_info['name']}")
                logger.info(f"简介: {gzh_info['signature']}")
                logger.info(f"FakeID: {gzh_info['fakeid']}")
                
                fakeid = gzh_info['fakeid']
                
                # 检查是否有已存在的数据文件
                safe_gzh_name = "".join(c for c in self.gzh_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                json_filename = os.path.join('static', 'mp_accounts', safe_gzh_name, f"{safe_gzh_name}.json")
                existing_data = self._load_existing_data(json_filename)
                
                # 如果搜索数量为0，直接进行全量搜索，不检查本地数据
                if self.max_articles == 0:
                    logger.info("搜索数量设置为0，直接进行全量搜索获取所有文章")
                    self.search_status = "进行全量搜索（获取所有文章）"
                    # 继续执行全量搜索逻辑，不return
                elif existing_data and existing_data.get('articles'):
                    existing_articles_count = len(existing_data.get('articles', []))
                    logger.info(f"发现已存在数据文件，已有 {existing_articles_count} 篇文章")
                    
                    # 检查是否需要全量搜索
                    if self.max_articles > existing_articles_count:
                        logger.info(f"需要搜索 {self.max_articles} 篇文章，超过已有的 {existing_articles_count} 篇，进行全量搜索")
                        self.search_status = f"需要更多文章，进行全量搜索（目标：{self.max_articles}篇）"
                        # 继续执行全量搜索逻辑，不return
                    else:
                        # 搜索数量不超过已有数量，直接返回已有数据的前N篇
                        logger.info(f"需要搜索 {self.max_articles} 篇文章，不超过已有的 {existing_articles_count} 篇，直接返回已有数据")
                        self.search_status = "使用已有数据"
                        self.articles_data = existing_data.get('articles', [])[:self.max_articles]
                        self.total_articles_fetched = len(self.articles_data)
                        self.search_status = f"搜索完成！共 {self.total_articles_fetched} 篇文章（来自已有数据）"
                        self.search_progress = 100
                        return
                
                # 获取第一页确定总数
                self.search_status = "获取文章列表中"
                first_page_data, api_type = self.get_articles(fakeid, 0, 5)
                if not first_page_data:
                    self.search_status = "获取第一页失败"
                    logger.error("获取第一页失败")
                    return
                
                logger.info(f"使用API类型: {api_type}")
                
                # 解析总文章数
                publish_page_data = json.loads(first_page_data.get('publish_page', '{}'))
                total_articles = publish_page_data.get('total_count', 0)
                
                if total_articles == 0:
                    logger.warning("无法确定文章总数，将继续获取直到没有更多文章")
                    total_pages = 1000  # 设置一个足够大的值
                else:
                    total_pages = (total_articles + 4) // 5
                    logger.info(f"该公众号共有 {total_articles} 篇文章，分为 {total_pages} 页")
                
                self.search_status = "正在获取文章"
                
                # 处理第一页数据
                page_articles = self._process_page_data(first_page_data, api_type, 1)
                self._add_articles(page_articles, 1)
                self.search_progress = min(1, 1 / total_pages * 100) if total_pages > 0 else 0
                
                # 逐页获取文章
                consecutive_empty_pages = 0
                max_empty_pages = 5  # 连续5页没有数据就停止
                
                for page_num in range(1, min(total_pages, 200)):  # 最多获取200页，避免无限循环
                    if not self.searching:
                        break
                    
                    # 检查是否达到数量限制
                    if self.max_articles > 0 and self.total_articles_fetched >= self.max_articles:
                        logger.info(f"已达到搜索数量限制: {self.max_articles}")
                        self.search_status = f"搜索完成！已达到数量限制 {self.max_articles} 篇"
                        break
                    
                    logger.info(f"获取第 {page_num + 1} 页...")
                    self.search_status = f"正在获取第 {page_num + 1} 页"
                    
                    offset = page_num * 5
                    page_data, current_api_type = self.get_articles(fakeid, offset, 5)
                    
                    if not page_data:
                        logger.error(f"第 {page_num + 1} 页获取失败")
                        consecutive_empty_pages += 1
                        if consecutive_empty_pages >= max_empty_pages:
                            logger.warning(f"连续{consecutive_empty_pages}页获取失败，停止搜索")
                            break
                        continue
                    
                    # 解析页面数据
                    page_articles = self._process_page_data(page_data, current_api_type, page_num + 1)
                    
                    if not page_articles:
                        consecutive_empty_pages += 1
                        logger.warning(f"第 {page_num + 1} 页无文章数据")
                        if consecutive_empty_pages >= max_empty_pages:
                            logger.warning(f"连续{consecutive_empty_pages}页无数据，可能已到末尾")
                            break
                    else:
                        consecutive_empty_pages = 0  # 重置计数器
                        self._add_articles(page_articles, page_num + 1)
                    
                    # 更新进度
                    self.search_progress = min(100, (page_num + 1) / total_pages * 100) if total_pages > 0 else 0
                    
                    # 每10页记录一次进度
                    if (page_num + 1) % 10 == 0:
                        logger.info(f"已获取 {page_num + 1} 页，累计 {self.total_articles_fetched} 篇文章")
                    
                    # 调用回调函数更新前端状态
                    if callback:
                        callback(self.get_search_status())
                
                self.search_status = f"搜索完成！共获取 {self.total_articles_fetched} 篇文章"
                self.search_progress = 100
                logger.info(f"搜索完成！总共获取了 {self.total_articles_fetched} 篇文章")
                
                # 保存结果
                self._save_results()
                
            except Exception as e:
                self.search_status = f"搜索过程中发生错误: {e}"
                logger.error(f"搜索过程中发生错误: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.searching = False
                if callback:
                    callback(self.get_search_status())
        
        # 启动搜索线程
        search_thread = Thread(target=_search, daemon=True)
        search_thread.start()
        return search_thread

    def _add_articles(self, page_articles, page_num):
        """添加文章到列表"""
        if page_articles:
            logger.info(f"第{page_num}页解析到 {len(page_articles)} 篇文章")
            for article in page_articles:
                # 检查是否达到数量限制
                if self.max_articles > 0 and self.total_articles_fetched >= self.max_articles:
                    logger.info(f"已达到搜索数量限制: {self.max_articles}")
                    break
                
                self.total_articles_fetched += 1
                logger.info(f"[{self.total_articles_fetched}] {article['title']}")
                self.articles_data.append(article)

    def _save_results(self):
        """保存搜索结果到公众号专用目录"""
        # 创建安全的文件夹名称
        safe_gzh_name = "".join(c for c in self.gzh_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        mp_dir = os.path.join('static', 'mp_accounts', safe_gzh_name)
        os.makedirs(mp_dir, exist_ok=True)
        
        # JSON文件以公众号名称命名
        json_filename = os.path.join(mp_dir, f"{safe_gzh_name}.json")
        
        # 对于增量搜索，self.articles_data已经包含了正确顺序的所有文章
        # （新文章在前，历史文章在后）
        total_articles = len(self.articles_data)
        
        results = {
            'gzh_name': self.gzh_name,
            'gzh_info': self.gzh_info,
            'total_articles': total_articles,
            'last_update_time': datetime.now().isoformat(),
            'fingerprint_used': self.fingerprint,
            'articles': self.articles_data
        }
        
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"结果已保存到: {json_filename}")
        logger.info(f"总文章数: {total_articles}")

    def _load_existing_data(self, json_filename):
        """加载已存在的数据文件"""
        if os.path.exists(json_filename):
            try:
                with open(json_filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载已存在数据失败: {e}")
        return None

    def _merge_articles(self, existing_articles, new_articles):
        """合并文章数据，新文章添加到开头，按时间排序"""
        # 创建已存在文章的标题集合，用于快速查找
        existing_titles = {article.get('title', '') for article in existing_articles}
        
        # 筛选出真正的新文章
        truly_new_articles = []
        for article in new_articles:
            if article.get('title', '') not in existing_titles:
                truly_new_articles.append(article)
        
        # 将新文章添加到开头，保持时间顺序（由近到远）
        merged = truly_new_articles + existing_articles
        
        # 按发布时间排序（由近到远）
        merged.sort(key=lambda x: x.get('update_time', 0), reverse=True)
        
        logger.info(f"合并文章: 已有{len(existing_articles)}篇, 新增{len(truly_new_articles)}篇")
        return merged

    def _incremental_search(self, fakeid, existing_articles, callback=None):
        """增量搜索，只获取新文章，优化版本"""
        # 创建已存在文章标题的集合，用于快速查找
        existing_titles = {article.get('title', '') for article in existing_articles}
        logger.info(f"已存在 {len(existing_articles)} 篇文章，开始增量搜索")
        
        new_articles_count = 0
        page_num = 0
        found_existing_article = False  # 标记是否找到已存在的文章
        
        while self.searching and not found_existing_article:
            # 检查是否达到数量限制
            if self.max_articles > 0 and self.total_articles_fetched >= self.max_articles:
                logger.info(f"已达到搜索数量限制: {self.max_articles}")
                break
            
            self.search_status = f"增量搜索第 {page_num + 1} 页"
            logger.info(f"增量搜索第 {page_num + 1} 页...")
            
            offset = page_num * 5
            page_data, api_type = self.get_articles(fakeid, offset, 5)
            
            if not page_data:
                logger.error(f"第 {page_num + 1} 页获取失败")
                break
            
            # 解析页面数据
            page_articles = self._process_page_data(page_data, api_type, page_num + 1)
            
            if not page_articles:
                logger.warning(f"第 {page_num + 1} 页无文章数据")
                break
            
            # 处理这一页的文章
            for article in page_articles:
                if article.get('title', '') not in existing_titles:
                    # 这是新文章，按时间顺序添加
                    if self.max_articles == 0 or self.total_articles_fetched < self.max_articles:
                        self.total_articles_fetched += 1
                        new_articles_count += 1
                        # 将新文章添加到列表末尾，稍后会统一排序
                        self.articles_data.append(article)
                        logger.info(f"[新增{new_articles_count}] {article['title']}")
                else:
                    # 找到已存在的文章，停止搜索
                    logger.info(f"找到已存在文章: {article['title']}")
                    logger.info("停止增量搜索，从历史JSON中获取剩余文章")
                    found_existing_article = True
                    break
            
            # 更新进度
            self.search_progress = min(100, (page_num + 1) * 10)  # 简单的进度计算
            
            # 调用回调函数
            if callback:
                callback(self.get_search_status())
            
            page_num += 1
            
            # 防止无限循环，最多搜索50页
            if page_num >= 50:
                logger.warning("已搜索50页，停止增量搜索")
                break
        
        # 如果找到了新文章，需要将新文章与历史文章合并
        if new_articles_count > 0:
            logger.info(f"增量搜索完成，新增 {new_articles_count} 篇文章")
            
            # 先对新文章按时间排序（由近到远）
            self.articles_data.sort(key=lambda x: x.get('update_time', 0), reverse=True)
            
            # 将新文章与历史文章合并，新文章在前
            merged_articles = self.articles_data + existing_articles
            
            # 对所有文章按时间重新排序（由近到远）
            merged_articles.sort(key=lambda x: x.get('update_time', 0), reverse=True)
            
            self.articles_data = merged_articles
            self.total_articles_fetched = len(self.articles_data)
            
            logger.info(f"合并完成，总文章数: {self.total_articles_fetched}")
            logger.info(f"最新文章: {self.articles_data[0].get('title') if self.articles_data else 'None'}")
        else:
            logger.info("未发现新文章")
        
        return new_articles_count

    def stop_search(self):
        """停止搜索"""
        self.searching = False
        self.search_status = "搜索已停止"
        logger.info("搜索已停止")

# 全局搜索器实例管理
active_searchers = {}

def create_searcher(gzh_name, token=None, max_articles=0):
    """创建搜索器实例"""
    searcher_id = f"{gzh_name}_{int(time.time())}"
    searcher = WebWeChatSearcher(gzh_name, token, max_articles)
    active_searchers[searcher_id] = searcher
    return searcher_id, searcher

def get_searcher(searcher_id):
    """获取搜索器实例"""
    return active_searchers.get(searcher_id)

def remove_searcher(searcher_id):
    """移除搜索器实例"""
    if searcher_id in active_searchers:
        active_searchers[searcher_id].stop_search()
        del active_searchers[searcher_id]

if __name__ == "__main__":
    # 测试代码
    gzh_name = input("请输入要搜索的公众号名称: ")
    if not gzh_name:
        print("公众号名称不能为空")
        exit()

    searcher = WebWeChatSearcher(gzh_name)
    if searcher.searching:
        def progress_callback(status):
            print(f"进度: {status['progress']:.1f}% - {status['status']}")
        
        thread = searcher.search_all_articles_async(progress_callback)
        thread.join()  # 等待搜索完成