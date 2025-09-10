import os
import time
import json
import pickle
import requests
from urllib.parse import urlparse, parse_qs
from fake_useragent import UserAgent
from threading import Thread
import sys
import re
import base64

class QRCodeDisplay(Thread):
    """显示二维码的线程类"""
    def __init__(self, image_content):
        super().__init__()
        self.image_content = image_content
        self.daemon = True  # 设置为守护线程，主线程结束时自动结束
        
    def run(self):
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(self.image_content))
            img.show()
        except Exception as e:
            print(f"显示二维码失败: {e}")
            print("请手动保存二维码并扫描")
            with open("qrcode.png", "wb") as f:
                f.write(self.image_content)
            print("二维码已保存为 qrcode.png")

class WeChatLoginAPI:
    """微信公众号登录API"""
    
    def __init__(self, cookie_path=None, cookie_json_path=None):
        """
        初始化微信公众号登录API
        
        Args:
            cookie_path: Cookies文件保存路径（兼容性保留，实际使用多账号管理）
            cookie_json_path: token和cookie信息的JSON文件保存路径（兼容性保留）
        """
        self.ua = UserAgent()
        self.headers = {
            'User-Agent': self.ua.random, 
            'Referer': "https://mp.weixin.qq.com/", 
            "Host": "mp.weixin.qq.com"
        }
        
        # 获取应用程序根目录
        if getattr(sys, 'frozen', False):
            # 打包后的应用程序
            base_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境
            base_dir = os.path.dirname(os.path.dirname(__file__))
        
        # 创建cookies目录
        self.cookies_dir = os.path.join(base_dir, 'cookies')
        if not os.path.exists(self.cookies_dir):
            os.makedirs(self.cookies_dir)
            
        # 设置默认路径（兼容性保留）
        self.cookie_path = cookie_path or os.path.join(self.cookies_dir, 'gzhcookies.cookie')
        self.cookie_json_path = cookie_json_path or os.path.join(self.cookies_dir, 'cookie.json')
        
        # 当前使用的账号token
        self.current_token = None
        
        print(f"Cookies 根目录: {self.cookies_dir}")
        
        # 初始化时自动清理过期账号
        self._cleanup_expired_accounts_on_init()
    
    def get_all_accounts(self):
        """
        获取所有可用的账号信息
        
        Returns:
            list: 包含所有账号信息的列表
        """
        accounts = []
        if not os.path.exists(self.cookies_dir):
            return accounts
            
        for item in os.listdir(self.cookies_dir):
            token_dir = os.path.join(self.cookies_dir, item)
            if os.path.isdir(token_dir):
                cookie_json_path = os.path.join(token_dir, 'cookie.json')
                if os.path.exists(cookie_json_path):
                    try:
                        with open(cookie_json_path, 'r', encoding='utf-8') as f:
                            account_info = json.load(f)
                        account_info['token_dir'] = token_dir
                        accounts.append(account_info)
                    except Exception as e:
                        print(f"读取账号 {item} 信息失败: {e}")
        
        return accounts
    
    def is_account_valid(self, account_info):
        """
        检查账号是否有效（时间和请求次数）
        
        Args:
            account_info: 账号信息字典
            
        Returns:
            bool: 账号是否有效
        """
        current_time = int(time.time())
        
        # 检查是否过期（88小时）
        if current_time > account_info.get('expire_time', 0):
            return False
        
        # 检查请求次数是否超限
        if self.get_current_request_count(account_info) >= 59:
            return False
            
        return True
    
    def get_current_request_count(self, account_info):
        """
        获取当前小时内的请求次数
        
        Args:
            account_info: 账号信息字典
            
        Returns:
            int: 当前小时内的请求次数
        """
        current_time = int(time.time())
        reset_time = account_info.get('request_reset_time', 0)
        
        # 如果已经过了重置时间，重置计数
        if current_time >= reset_time:
            return 0
        
        return account_info.get('request_count', 0)
    
    def update_request_count(self, token, increment=1):
        """
        更新指定账号的请求次数
        
        Args:
            token: 账号token
            increment: 增加的请求次数，默认为1
        """
        token_dir = os.path.join(self.cookies_dir, token)
        cookie_json_path = os.path.join(token_dir, 'cookie.json')
        
        if not os.path.exists(cookie_json_path):
            return
        
        try:
            with open(cookie_json_path, 'r', encoding='utf-8') as f:
                account_info = json.load(f)
            
            current_time = int(time.time())
            reset_time = account_info.get('request_reset_time', 0)
            
            # 如果已经过了重置时间，重置计数
            if current_time >= reset_time:
                account_info['request_count'] = 0
                account_info['request_reset_time'] = current_time + 3600  # 下一小时
                account_info['request_history'] = []
            
            # 更新请求次数
            account_info['request_count'] = account_info.get('request_count', 0) + increment
            
            # 记录请求历史
            if 'request_history' not in account_info:
                account_info['request_history'] = []
            account_info['request_history'].append(current_time)
            
            # 只保留最近1小时的历史记录
            account_info['request_history'] = [
                t for t in account_info['request_history'] 
                if current_time - t < 3600
            ]
            
            # 保存更新后的信息
            with open(cookie_json_path, 'w', encoding='utf-8') as f:
                json.dump(account_info, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"更新请求次数失败: {e}")
    
    def get_best_account(self):
        """
        获取最佳可用账号（有效且请求次数最少）
        
        Returns:
            dict: 最佳账号信息，如果没有可用账号返回None
        """
        accounts = self.get_all_accounts()
        valid_accounts = [acc for acc in accounts if self.is_account_valid(acc)]
        
        if not valid_accounts:
            return None
        
        # 按请求次数排序，选择请求次数最少的账号
        best_account = min(valid_accounts, key=lambda x: self.get_current_request_count(x))
        return best_account
    
    def switch_to_best_account(self):
        """
        切换到最佳可用账号
        
        Returns:
            str: 切换到的账号token，如果没有可用账号返回None
        """
        best_account = self.get_best_account()
        if best_account:
            self.current_token = best_account['token']
            print(f"切换到账号: {self.current_token[:10]}...")
            return self.current_token
        else:
            print("没有可用的账号")
            return None

    def is_login(self, session):
        """
        检查当前会话是否已登录
        
        Args:
            session: requests.Session对象
            
        Returns:
            tuple: (session, 是否已登录)
        """
        try:
            session.cookies.load(ignore_discard=True)
        except Exception:
            pass
            
        login_url = session.get(
            "https://mp.weixin.qq.com/cgi-bin/scanloginqrcode?action=ask&token=&lang=zh_CN&f=json&ajax=1"
        ).json()
        
        if login_url['base_resp']['ret'] == 0:
            print('Cookies值有效，无需扫码登录！')
            return session, True
        else:
            print('Cookies值已经失效，请重新扫码登录！')
            return session, False
    
    def check_cookie_valid(self, token=None):
        """
        快速检查 cookie 是否有效，支持多账号管理
        
        Args:
            token: 指定要检查的账号token，如果为None则检查最佳账号
            
        Returns:
            dict: 如果 cookie 有效，返回包含 token 和 cookie 的字典；否则返回 None
        """
        try:
            # 如果没有指定token，获取最佳账号
            if token is None:
                best_account = self.get_best_account()
                if not best_account:
                    return None
                token = best_account['token']
                self.current_token = token
            
            # 构建账号路径
            token_dir = os.path.join(self.cookies_dir, token)
            cookie_path = os.path.join(token_dir, 'gzhcookies.cookie')
            cookie_json_path = os.path.join(token_dir, 'cookie.json')
            
            if not os.path.exists(cookie_json_path):
                return None
            
            # 读取账号信息
            with open(cookie_json_path, 'r', encoding='utf-8') as f:
                account_info = json.load(f)
            
            # 检查账号是否有效
            if not self.is_account_valid(account_info):
                return None
            
            # 检查cookie文件是否存在
            if os.path.exists(cookie_path):
                return account_info
            
            return None
        except Exception as e:
            print(f"检查 cookie 有效性失败: {e}")
            return None
    
    def login(self):
        """
        登录微信公众号，支持多账号管理
        
        Returns:
            dict: 包含token和cookie的字典
        """
        # 首先尝试获取最佳可用账号
        login_info = self.check_cookie_valid()
        if login_info:
            print(f"使用现有账号: {login_info['token'][:10]}...")
            return login_info
        
        # 如果没有可用账号，执行完整的登录流程
        print("没有可用账号，开始登录流程...")
        return self.perform_login()
    
    def perform_login(self, qrcode_callback=None, status_callback=None):
        """
        执行完整的登录流程，包括二维码扫描
        
        Args:
            qrcode_callback: 二维码准备就绪时的回调函数，接收二维码图片内容
            status_callback: 状态更新时的回调函数，接收状态消息
            
        Returns:
            dict: 包含token和cookie的字典
        """
        session = requests.session()
        
        # 初始化登录会话
        session.get('https://mp.weixin.qq.com/', headers=self.headers)
        session.post(
            'https://mp.weixin.qq.com/cgi-bin/bizlogin?action=startlogin',
            data='userlang=zh_CN&redirect_url=&login_type=3&sessionid={}&token=&lang=zh_CN&f=json&ajax=1'.format(
                int(time.time() * 1000)
            ), 
            headers=self.headers
        )
        
        # 获取登录二维码
        login_url = session.get(
            'https://mp.weixin.qq.com/cgi-bin/scanloginqrcode?action=getqrcode&random={}'.format(
                int(time.time() * 1000)
            )
        )
        
        # 保存二维码到cookies文件夹
        qr_code_path = os.path.join(os.path.dirname(self.cookie_path), 'qrcode.png')
        with open(qr_code_path, 'wb') as f:
            f.write(login_url.content)
        
        # 处理二维码显示
        if qrcode_callback:
            qrcode_callback(login_url.content)
        else:
            # 默认显示二维码
            qr_display = QRCodeDisplay(login_url.content)
            qr_display.start()
        
        # 轮询登录状态
        date_url = 'https://mp.weixin.qq.com/cgi-bin/scanloginqrcode?action=ask&token=&lang=zh_CN&f=json&ajax=1'
        while True:
            try:
                date = session.get(date_url).json()
                if date['status'] == 0:
                    message = '二维码未失效，请扫码！'
                    if status_callback:
                        status_callback(message)
                    else:
                        print(message)
                elif date['status'] == 6:
                    message = '已扫码，请确认！'
                    if status_callback:
                        status_callback(message)
                    else:
                        print(message)
                elif date['status'] == 1:
                    message = '已确认，登录成功！'
                    if status_callback:
                        status_callback(message)
                    else:
                        print(message)
                    
                    # 完成登录
                    url = session.post(
                        'https://mp.weixin.qq.com/cgi-bin/bizlogin?action=login',
                        data='userlang=zh_CN&redirect_url=&cookie_forbidden=0&cookie_cleaned=1&plugin_used=0&login_type=3&token=&lang=zh_CN&f=json&ajax=1',
                        headers=self.headers
                    ).json()
                    
                    # 解析token
                    token = parse_qs(urlparse(url['redirect_url']).query).get('token', [None])[0]
                    session.get('https://mp.weixin.qq.com{}'.format(url['redirect_url']), headers=self.headers)
                    
                    # 保存cookies和token信息
                    cookie = '; '.join([f"{name}={value}" for name, value in session.cookies.items()])
                    
                    # 创建以token为名的子文件夹
                    token_dir = os.path.join(os.path.dirname(self.cookie_path), token)
                    os.makedirs(token_dir, exist_ok=True)
                    
                    # 保存cookie文件到子文件夹
                    token_cookie_path = os.path.join(token_dir, 'gzhcookies.cookie')
                    with open(token_cookie_path, 'wb') as f:
                        pickle.dump(session.cookies, f)
                    
                    # 获取公众号信息
                    account_info = self.get_account_info(token, cookie)
                    
                    # 创建包含完整信息的login_info
                    current_time = int(time.time())
                    login_info = {
                        'token': token,
                        'cookie': cookie,
                        'created_time': current_time,
                        'expire_time': current_time + 88 * 3600,  # 88小时后过期
                        'request_count': 0,  # 当前小时内请求次数
                        'request_reset_time': current_time + 3600,  # 下次重置请求计数的时间
                        'request_history': [],  # 请求历史记录
                        'name': account_info['name'],  # 公众号名称
                        'avatar': account_info['avatar'],  # 头像路径或base64
                        'avatar_url': account_info['avatar_url']  # 头像URL
                    }
                    
                    # 保存到子文件夹的cookie.json
                    token_json_path = os.path.join(token_dir, 'cookie.json')
                    with open(token_json_path, 'w', encoding='utf-8') as f:
                        json.dump(login_info, f, ensure_ascii=False, indent=2)
                    
                    # 删除二维码文件
                    try:
                        if os.path.exists(qr_code_path):
                            os.remove(qr_code_path)
                    except Exception as e:
                        print(f"删除二维码文件失败: {e}")
                    
                    return login_info
                    
                time.sleep(3)  # 等待3秒后再次检查状态
                
            except Exception as e:
                error_message = f"登录过程中发生错误: {e}"
                if status_callback:
                    status_callback(error_message)
                else:
                    print(error_message)
                time.sleep(3)
    
    def get_session(self, auto_switch=True):
        """
        获取已登录的会话对象，支持多账号管理和自动切换
        
        Args:
            auto_switch: 是否自动切换到最佳账号，默认为True
            
        Returns:
            requests.Session: 已登录的会话对象，如果登录失败返回None
        """
        # 如果启用自动切换，检查当前账号是否需要切换
        if auto_switch and self.current_token:
            current_account = self.check_cookie_valid(self.current_token)
            if not current_account or self.get_current_request_count(current_account) >= 59:
                print("当前账号不可用或请求次数已达上限，尝试切换账号...")
                self.switch_to_best_account()
        
        login_info = self.login()
        
        # 检查登录是否成功
        if not login_info or not login_info.get('token') or not login_info.get('cookie'):
            return None
        
        # 更新当前使用的token
        self.current_token = login_info['token']
        
        # 创建会话对象
        session = requests.session()
        
        # 从对应的cookie文件加载cookies
        token_dir = os.path.join(self.cookies_dir, login_info['token'])
        cookie_path = os.path.join(token_dir, 'gzhcookies.cookie')
        
        if os.path.exists(cookie_path):
            try:
                with open(cookie_path, 'rb') as f:
                    session.cookies = pickle.load(f)
            except Exception as e:
                print(f"加载cookie文件失败: {e}")
                # 备用方案：从字符串解析cookies
                for cookie_item in login_info['cookie'].split('; '):
                    if '=' in cookie_item:
                        name, value = cookie_item.split('=', 1)
                        session.cookies.set(name, value)
        else:
            # 从字符串解析cookies
            for cookie_item in login_info['cookie'].split('; '):
                if '=' in cookie_item:
                    name, value = cookie_item.split('=', 1)
                    session.cookies.set(name, value)
        
        # 设置headers
        session.headers.update(self.headers)
        
        # 更新请求计数
        self.update_request_count(login_info['token'])
        
        return session
    
    def login_with_callbacks(self, qrcode_callback=None, status_callback=None):
        """
        使用回调函数进行登录，适用于需要自定义二维码显示和状态更新的场景
        
        Args:
            qrcode_callback: 二维码准备就绪时的回调函数，接收二维码图片内容
            status_callback: 状态更新时的回调函数，接收状态消息
            
        Returns:
            dict: 包含token和cookie的字典
        """
        # 先检查是否已经登录
        login_info = self.check_cookie_valid()
        if login_info and login_info.get('token'):
            if status_callback:
                status_callback('已登录，无需重新扫码')
            return login_info
        
        # 执行完整的登录流程
        return self.perform_login(qrcode_callback, status_callback)
    
    def get_account_status(self):
        """
        获取所有账号的状态信息
        
        Returns:
            list: 包含所有账号状态的列表
        """
        accounts = self.get_all_accounts()
        status_list = []
        
        for account in accounts:
            current_time = int(time.time())
            request_count = self.get_current_request_count(account)
            
            status = {
                'token': account['token'][:10] + '...',
                'created_time': account.get('created_time', 0),
                'expire_time': account.get('expire_time', 0),
                'is_expired': current_time > account.get('expire_time', 0),
                'request_count': request_count,
                'request_limit_reached': request_count >= 59,
                'is_valid': self.is_account_valid(account),
                'hours_remaining': max(0, (account.get('expire_time', 0) - current_time) / 3600)
            }
            status_list.append(status)
        
        return status_list
    
    def cleanup_expired_accounts(self):
        """
        清理过期的账号文件夹
        
        Returns:
            int: 清理的账号数量
        """
        accounts = self.get_all_accounts()
        current_time = int(time.time())
        cleaned_count = 0
        
        for account in accounts:
            if current_time > account.get('expire_time', 0):
                try:
                    token_dir = account['token_dir']
                    import shutil
                    shutil.rmtree(token_dir)
                    print(f"清理过期账号: {account['token'][:10]}...")
                    cleaned_count += 1
                except Exception as e:
                    print(f"清理账号失败: {e}")
        
        return cleaned_count
    
    def _cleanup_expired_accounts_on_init(self):
        """
        初始化时清理过期账号的内部方法
        """
        try:
            if not os.path.exists(self.cookies_dir):
                return
            
            current_time = int(time.time())
            cleaned_count = 0
            
            # 遍历cookies目录下的所有子文件夹
            for item in os.listdir(self.cookies_dir):
                token_dir = os.path.join(self.cookies_dir, item)
                
                # 跳过非目录项
                if not os.path.isdir(token_dir):
                    continue
                
                cookie_json_path = os.path.join(token_dir, 'cookie.json')
                
                # 如果没有cookie.json文件，删除该文件夹
                if not os.path.exists(cookie_json_path):
                    try:
                        import shutil
                        shutil.rmtree(token_dir)
                        print(f"清理无效账号文件夹: {item}")
                        cleaned_count += 1
                    except Exception as e:
                        print(f"清理无效账号文件夹失败 {item}: {e}")
                    continue
                
                # 检查账号是否过期
                try:
                    with open(cookie_json_path, 'r', encoding='utf-8') as f:
                        account_info = json.load(f)
                    
                    expire_time = account_info.get('expire_time', 0)
                    
                    # 如果账号已过期，删除整个文件夹
                    if current_time > expire_time:
                        import shutil
                        shutil.rmtree(token_dir)
                        print(f"清理过期账号: {item[:10]}... (过期时间: {time.ctime(expire_time)})")
                        cleaned_count += 1
                        
                except Exception as e:
                    print(f"检查账号 {item} 时发生错误: {e}")
                    # 如果读取失败，也删除该文件夹
                    try:
                        import shutil
                        shutil.rmtree(token_dir)
                        print(f"清理损坏的账号文件夹: {item}")
                        cleaned_count += 1
                    except Exception as cleanup_error:
                        print(f"清理损坏账号文件夹失败 {item}: {cleanup_error}")
            
            if cleaned_count > 0:
                print(f"初始化清理完成，共清理 {cleaned_count} 个无效/过期账号")
            else:
                print("初始化检查完成，所有账号均有效")
                
        except Exception as e:
            print(f"初始化清理过期账号时发生错误: {e}")

    def logout_by_token(self, token):
        """
        通过 token 删除对应账号的 cookies 目录，实现登出。

        Args:
            token (str): 账号 token

        Returns:
            bool: 是否删除成功（或目录不存在视作成功）
        """
        try:
            if not token:
                return False
            token_dir = os.path.join(self.cookies_dir, token)
            if os.path.exists(token_dir) and os.path.isdir(token_dir):
                import shutil
                shutil.rmtree(token_dir)
                if self.current_token == token:
                    self.current_token = None
                return True
            # 目录不存在也视为成功
            return True
        except Exception as e:
            print(f"登出失败，删除目录出错: {e}")
            return False

    def get_account_info(self, token, cookie):
        """
        获取公众号信息（名称和头像）
        
        Args:
            token (str): 登录token
            cookie (str): 登录cookie
            
        Returns:
            dict: 包含name和avatar的字典，失败时返回默认值
        """
        try:
            # 设置请求头
            headers = {
                'User-Agent': self.ua.random,
                'Referer': "https://mp.weixin.qq.com/",
                "Host": "mp.weixin.qq.com",
                "Cookie": cookie
            }
            
            # 请求公众号首页获取信息
            response = requests.get(
                f'https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=zh_CN&token={token}', 
                headers=headers,
                timeout=10
            )
            
            # 解析响应内容
            if response.status_code == 200:
                print("已获取公众号信息响应")
                content = response.text
                
                # 查找 window.wx.commonData 对象
                match = re.search(r'window\.wx\.commonData\s*=\s*({[\s\S]*?});', content)
                
                if match:
                    # 提取 JavaScript 对象字符串
                    js_obj_str = match.group(1)
                    
                    # 使用正则提取 nick_name
                    nick_name_match = re.search(r'nick_name:\s*"([^"]+)"', js_obj_str)
                    if nick_name_match:
                        gzh_name = nick_name_match.group(1)
                        print(f"成功获取公众号名称: {gzh_name}")
                        
                        # 获取头像URL
                        head_img_match = re.search(r'head_img:\s*\'([^\']+)\'', js_obj_str)
                        avatar_url = ""
                        avatar_path = ""
                        
                        if head_img_match:
                            avatar_url = head_img_match.group(1)
                            if not avatar_url.startswith('https://'):
                                avatar_url = avatar_url.replace('http://', 'https://')
                            print(f"获取到头像URL: {avatar_url}")
                            
                            # 下载并保存头像到token文件夹
                            avatar_path = self._download_avatar(token, avatar_url)
                        
                        return {
                            'name': gzh_name,
                            'avatar': avatar_path or self._get_default_avatar(),
                            'avatar_url': avatar_url
                        }
                
                # 尝试其他方式查找公众号名称
                gzh_name_match = re.search(r'var nickname\s*=\s*"([^"]+)"', content)
                if gzh_name_match:
                    gzh_name = gzh_name_match.group(1)
                    print(f"通过备用方式找到公众号名称: {gzh_name}")
                    
                    # 查找头像URL
                    head_img_match = re.search(r'var headimg\s*=\s*"([^"]+)"', content)
                    avatar_url = ""
                    avatar_path = ""
                    
                    if head_img_match:
                        avatar_url = head_img_match.group(1)
                        if not avatar_url.startswith('https://'):
                            avatar_url = avatar_url.replace('http://', 'https://')
                        
                        # 下载并保存头像
                        avatar_path = self._download_avatar(token, avatar_url)
                    
                    return {
                        'name': gzh_name,
                        'avatar': avatar_path or self._get_default_avatar(),
                        'avatar_url': avatar_url
                    }
            else:
                print(f"获取公众号信息失败: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"获取公众号信息出错: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # 返回默认值
        return {
            'name': '公众号',
            'avatar': self._get_default_avatar(),
            'avatar_url': ''
        }
    
    def _download_avatar(self, token, avatar_url):
        """
        下载头像并保存到token文件夹
        
        Args:
            token (str): 登录token
            avatar_url (str): 头像URL
            
        Returns:
            str: 保存的头像文件路径，失败时返回空字符串
        """
        try:
            if not avatar_url:
                return ""
            
            # 构建保存路径
            token_dir = os.path.join(self.cookies_dir, token)
            avatar_path = os.path.join(token_dir, 'avatar.jpg')
            
            # 下载头像
            response = requests.get(avatar_url, timeout=10)
            if response.status_code == 200:
                with open(avatar_path, 'wb') as f:
                    f.write(response.content)
                print(f"头像已保存到: {avatar_path}")
                return avatar_path
            else:
                print(f"下载头像失败: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"下载头像出错: {str(e)}")
        
        return ""
    
    def _get_default_avatar(self):
        """
        获取默认头像的base64编码
        
        Returns:
            str: 默认头像的data URL
        """
        svg_content = """
        <svg xmlns='http://www.w3.org/2000/svg' width='48' height='48' viewBox='0 0 48 48'>
            <circle cx='24' cy='24' r='24' fill='#07c160'/>
            <text x='24' y='30' text-anchor='middle' font-family='Arial' font-size='16' fill='white' font-weight='bold'>微</text>
        </svg>
        """
        return 'data:image/svg+xml;base64,' + base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')

# 使用示例
def get_wechat_login():
    """
    获取微信公众号登录API实例
    
    Returns:
        WeChatLoginAPI: 微信公众号登录API实例
    """
    return WeChatLoginAPI()