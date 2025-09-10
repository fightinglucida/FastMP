#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终版微信公众号搜索器
简化数据处理，专注于稳定性
"""

import time
import random
import requests
import os
import json
import csv
import hashlib
from datetime import datetime
from urllib.parse import quote

class FinalWeChatSearcher:
    """
    最终版搜索器 - 简化且稳定
    """
    
    def __init__(self, gzh_name):
        self.gzh_name = gzh_name
        self.searching = True
        self.total_articles_fetched = 0
        self.session = requests.Session()
        self.articles_data = []
        
        # 生成32位fingerprint
        self.fingerprint = self._generate_fingerprint()
        
        try:
            self.login_info = self._load_cookie()
            self._setup_session()
            print(f"🔐 生成的32位Fingerprint: {self.fingerprint}")
        except Exception as e:
            print(f"初始化失败: {e}")
            self.searching = False

    def _generate_fingerprint(self):
        """生成32位fingerprint"""
        # 使用时间戳和随机数生成稳定的fingerprint
        timestamp = int(time.time() * 1000)
        random_part = random.randint(100000, 999999)
        combined = f"fingerprint_{timestamp}_{random_part}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()

    def _load_cookie(self):
        """加载Cookie"""
        cookies_dir = 'cookies'
        sub_dirs = [d for d in os.listdir(cookies_dir) if os.path.isdir(os.path.join(cookies_dir, d))]
        account_dir = os.path.join(cookies_dir, sub_dirs[0])
        cookie_file_path = os.path.join(account_dir, 'cookie.json')

        with open(cookie_file_path, 'r', encoding='utf-8') as f:
            login_info = json.load(f)
            
        print(f"✅ 加载Cookie账号: {os.path.basename(account_dir)}")
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
            time.sleep(random.uniform(1.0, 2.0))
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'base_resp' in data:
                        ret_code = data['base_resp'].get('ret', 0)
                        if ret_code == 0:
                            return data
                        elif ret_code == 200013:
                            print(f"⚠️ 遇到200013错误，重新生成fingerprint")
                            self.fingerprint = self._generate_fingerprint()
                            print(f"🔄 新fingerprint: {self.fingerprint}")
                            return None
                        else:
                            print(f"❌ API错误: {ret_code}")
                            return None
                    else:
                        return data
                except json.JSONDecodeError:
                    print(f"❌ JSON解析失败")
                    return None
            else:
                print(f"❌ HTTP错误: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return None

    def search_gzh(self, gzh_name):
        """搜索公众号"""
        encoded_name = quote(gzh_name)
        search_url = f'https://mp.weixin.qq.com/cgi-bin/searchbiz?action=search_biz&token={self.login_info["token"]}&lang=zh_CN&f=json&ajax=1&random={time.time()}&query={encoded_name}&begin=0&count=5&fingerprint={self.fingerprint}'
        
        data = self._make_request(search_url)
        if not data or not data.get('list'):
            return None

        gzh_data = data['list'][0]
        return {
            'name': gzh_data['nickname'],
            'fakeid': gzh_data['fakeid'],
            'avatar_url': gzh_data['round_head_img'],
            'signature': gzh_data['signature']
        }

    def get_articles(self, fakeid, begin=0, count=5):
        """获取文章列表"""
        
        # 使用新接口
        new_url = f'https://mp.weixin.qq.com/cgi-bin/appmsgpublish?sub=list&search_field=null&begin={begin}&count={count}&query=&fakeid={fakeid}&type=101_1&free_publish_type=1&sub_action=list_ex&fingerprint={self.fingerprint}&token={self.login_info["token"]}&lang=zh_CN&f=json&ajax=1'
        
        data = self._make_request(new_url)
        if data:
            return data, 'new'
        
        return None, None

    def _process_page_data(self, data, api_type, page_num):
        """处理页面数据 - 根据新API格式解析"""
        page_articles = []
        
        try:
            # 只处理新接口数据
            if api_type == 'new' and 'publish_page' in data:
                try:
                    # 解析publish_page字符串
                    publish_page_data = json.loads(data['publish_page'])
                    
                    # 获取文章统计信息
                    total_count = publish_page_data.get('total_count', 0)
                    publish_count = publish_page_data.get('publish_count', 0)
                    masssend_count = publish_page_data.get('masssend_count', 0)
                    
                    print(f"   � 统计信息:")
                    print(f"      总文章数: {total_count}")
                    print(f"      发表总数: {publish_count}")
                    print(f"      群发总数: {masssend_count}")
                    
                    # 处理文章列表
                    if 'publish_list' in publish_page_data:
                        for item in publish_page_data['publish_list']:
                            if isinstance(item, dict) and 'publish_info' in item:
                                try:
                                    # 解析每篇文章的publish_info
                                    publish_info = json.loads(item['publish_info'])
                                    if 'appmsgex' in publish_info and publish_info['appmsgex']:
                                        # 提取文章信息
                                        for article in publish_info['appmsgex']:
                                            article_data = {
                                                'title': article.get('title', '无标题'),
                                                'cover': article.get('cover', ''),
                                                'content_url': article.get('link', ''),
                                                'update_time': article.get('update_time', 0),
                                                'itemidx': article.get('itemidx', 0),
                                                'author': article.get('author_name', ''),
                                                'digest': article.get('digest', ''),
                                                'publish_time': datetime.fromtimestamp(article.get('update_time', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                                                'publish_type': item.get('publish_type', 0)
                                            }
                                            page_articles.append(article_data)
                                except json.JSONDecodeError:
                                    print(f"   ⚠️ 解析文章信息失败")
                                    continue
                
                except json.JSONDecodeError as e:
                    print(f"   ❌ 解析publish_page失败: {e}")
            
            # 如果没有找到文章，输出调试信息
            if not page_articles:
                print(f"   ⚠️ 未找到文章数据")
                print(f"   数据样本: {str(data)[:300]}...")
        
        except Exception as e:
            print(f"   ❌ 处理第{page_num}页数据失败: {e}")
        
        return page_articles

    def _extract_article_from_dict(self, item):
        """从字典中提取文章信息"""
        try:
            # 尝试多种可能的字段名
            title = item.get('title') or item.get('subject') or '无标题'
            
            # 如果有publish_info字段，尝试解析
            if 'publish_info' in item:
                try:
                    publish_info_str = item['publish_info']
                    if isinstance(publish_info_str, str):
                        publish_info = json.loads(publish_info_str)
                        if 'appmsgex' in publish_info and publish_info['appmsgex']:
                            # 取第一篇文章
                            appmsg = publish_info['appmsgex'][0]
                            return {
                                'title': appmsg.get('title', title),
                                'digest': appmsg.get('digest', ''),
                                'content_url': appmsg.get('content_url', ''),
                                'source_url': appmsg.get('source_url', ''),
                                'cover': appmsg.get('cover', ''),
                                'author': appmsg.get('author', ''),
                                'copyright_stat': appmsg.get('copyright_stat', 0),
                                'duration': appmsg.get('duration', 0),
                                'type': 'main',
                                'publish_time': datetime.fromtimestamp(item.get('sent_info', {}).get('time', 0)).strftime('%Y-%m-%d %H:%M:%S') if isinstance(item.get('sent_info'), dict) and item.get('sent_info', {}).get('time') else '未知时间',
                                'publish_timestamp': item.get('sent_info', {}).get('time', 0) if isinstance(item.get('sent_info'), dict) else 0,
                                'msgid': item.get('msgid', ''),
                                'publish_type': item.get('publish_type', 0)
                            }
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass
            
            # 如果没有publish_info或解析失败，直接从item提取
            if title != '无标题':
                return {
                    'title': title,
                    'digest': item.get('digest', ''),
                    'content_url': item.get('link', item.get('content_url', '')),
                    'source_url': item.get('source_url', ''),
                    'cover': item.get('cover', ''),
                    'author': item.get('author', ''),
                    'copyright_stat': item.get('copyright_stat', 0),
                    'duration': item.get('duration', 0),
                    'type': 'main',
                    'publish_time': datetime.fromtimestamp(item.get('create_time', item.get('time', 0))).strftime('%Y-%m-%d %H:%M:%S') if item.get('create_time', item.get('time', 0)) else '未知时间',
                    'publish_timestamp': item.get('create_time', item.get('time', 0)),
                    'msgid': item.get('msgid', ''),
                    'publish_type': item.get('publish_type', 0)
                }
        
        except Exception as e:
            print(f"   ⚠️ 提取文章信息失败: {e}")
        
        return None

    def search_all_articles(self):
        """搜索所有文章"""
        if not self.searching:
            return
            
        try:
            # 搜索公众号
            print(f"🔍 搜索公众号: {self.gzh_name}")
            gzh_info = self.search_gzh(self.gzh_name)
            if not gzh_info:
                print(f"❌ 未找到公众号: {self.gzh_name}")
                return
            
            print(f"✅ 找到公众号: {gzh_info['name']}")
            print(f"   简介: {gzh_info['signature']}")
            print(f"   FakeID: {gzh_info['fakeid']}")
            print("=" * 60)
            
            fakeid = gzh_info['fakeid']
            
            # 获取第一页确定总数和API类型
            first_page_data, api_type = self.get_articles(fakeid, 0, 5)
            if not first_page_data:
                print("❌ 获取第一页失败")
                return
            
            print(f"📡 使用API类型: {api_type}")
            
            # 解析总文章数
            publish_page_data = json.loads(first_page_data.get('publish_page', '{}'))
            total_articles = publish_page_data.get('total_count', 0)
            
            if total_articles == 0:
                print("⚠️ 无法确定文章总数，将继续获取直到没有更多文章")
                total_pages = 1000  # 设置一个足够大的值
            else:
                total_pages = (total_articles + 4) // 5
                print(f"📊 该公众号共有 {total_articles} 篇文章，分为 {total_pages} 页")
            
            print("🚀 开始获取文章...")
            print("=" * 60)
            
            # 处理第一页数据
            page_articles = self._process_page_data(first_page_data, api_type, 1)
            self._display_articles(page_articles, 1)
            
            # 逐页获取文章，获取所有页面直到结束
            for page_num in range(1, total_pages):
                if not self.searching:
                    break
                
                print(f"📄 获取第 {page_num + 1} 页...")
                
                offset = page_num * 5
                page_data, current_api_type = self.get_articles(fakeid, offset, 5)
                
                if not page_data:
                    print(f"❌ 第 {page_num + 1} 页获取失败")
                    break
                
                # 解析页面数据
                page_articles = self._process_page_data(page_data, current_api_type, page_num + 1)
                
                # 如果连续3次没有获取到文章，则认为已经到达末尾
                if not page_articles:
                    print(f"⚠️ 第 {page_num + 1} 页无文章数据")
                    # 再尝试3次
                    retry_count = 0
                    for _ in range(3):
                        time.sleep(2)  # 等待2秒后重试
                        page_data, current_api_type = self.get_articles(fakeid, offset, 5)
                        if page_data:
                            page_articles = self._process_page_data(page_data, current_api_type, page_num + 1)
                            if page_articles:
                                break
                        retry_count += 1
                    
                    if retry_count >= 3:
                        print(f"⚠️ 连续{retry_count}次未获取到文章，可能已到末尾")
                        break
                
                self._display_articles(page_articles, page_num + 1)
                
                # 每10页显示进度
                if (page_num + 1) % 10 == 0:
                    print(f"📈 已获取 {page_num + 1} 页，累计 {self.total_articles_fetched} 篇文章")
                
                # 用户控制
                if (page_num + 1) % 20 == 0:
                    user_input = input(f"\n已获取{page_num + 1}页，继续？(回车=继续, q=退出): ")
                    if user_input.lower() == 'q':
                        break
            
            print(f"\n🎉 搜索完成！")
            print(f"   总共获取了 {self.total_articles_fetched} 篇文章")
            
            # 保存结果
            self._save_results()
            
        except Exception as e:
            print(f"❌ 搜索过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.searching = False

    def _display_articles(self, page_articles, page_num):
        """显示文章信息"""
        if page_articles:
            print(f"   ✅ 解析到 {len(page_articles)} 篇文章")
            for article in page_articles:
                self.total_articles_fetched += 1
                print(f"      [{self.total_articles_fetched}] {article['title']}")
                print(f"          发布时间: {article['publish_time']}")
                if article['author']:
                    print(f"          作者: {article['author']}")
                print()
                
                self.articles_data.append(article)

    def _save_results(self):
        """保存搜索结果"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 保存JSON格式
        json_filename = f"final_search_{self.gzh_name}_{timestamp}.json"
        results = {
            'gzh_name': self.gzh_name,
            'total_articles': self.total_articles_fetched,
            'search_time': datetime.now().isoformat(),
            'fingerprint_used': self.fingerprint,
            'articles': self.articles_data
        }
        
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # 保存CSV格式
        csv_filename = f"final_search_{self.gzh_name}_{timestamp}.csv"
        with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['序号', '标题', '发布时间', '作者', '摘要', '链接'])
            
            for i, article in enumerate(self.articles_data, 1):
                writer.writerow([
                    i,
                    article['title'],
                    article['publish_time'],
                    article['author'],
                    article['digest'],
                    article['content_url']
                ])
        
        print(f"💾 结果已保存:")
        print(f"   JSON: {json_filename}")
        print(f"   CSV:  {csv_filename}")

def main():
    """主函数"""
    print("🚀 最终版微信公众号搜索器")
    print("✅ 双接口支持，自动切换")
    print("✅ 32位fingerprint生成")
    print("✅ 稳定的数据解析")
    print("=" * 60)
    
    gzh_name = input("请输入要搜索的公众号名称: ")
    if not gzh_name:
        print("❌ 公众号名称不能为空")
        return

    try:
        searcher = FinalWeChatSearcher(gzh_name)
        if searcher.searching:
            searcher.search_all_articles()
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断搜索")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")

if __name__ == "__main__":
    main()