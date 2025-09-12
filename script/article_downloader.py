import os
import re
import time
import threading
import requests
import traceback
import logging
from queue import Queue, Empty
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from PyQt6.QtCore import QObject, pyqtSignal
from datetime import datetime

class WeChatArticleDownloader:
    """微信文章下载器，负责下载单篇文章"""
    
    def __init__(self, save_dir="."):
        self.save_dir = save_dir
        self.images_dir = os.path.join(save_dir, "images")
        os.makedirs(self.images_dir, exist_ok=True)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        # 当前文章标题
        self.current_article_title = None
        # 当前文章发布时间
        self.current_publish_time = ""
        # 设置日志
        self._setup_logger()
        
    def _setup_logger(self):
        """设置日志记录器"""
        self.logger = logging.getLogger("WeChatArticleDownloader")
        self.logger.setLevel(logging.INFO)
        
        # 清除所有已存在的处理器
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 设置日志格式
        formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(formatter)
        
        # 添加处理器到日志记录器
        self.logger.addHandler(console_handler)
        
    def download_article(self, url):
        """下载文章并保存为Markdown格式
        
        Args:
            url: 文章链接
            
        Returns:
            tuple: (是否成功, 文件路径)
        """
        try:
            # 获取文章内容
            title, content = self.get_article_content(url)
            
            if title and content:
                # 保存为Markdown文件
                file_path = self.save_to_markdown(title, content)
                if file_path:
                    return True, file_path
            
            return False, None
            
        except Exception as e:
            self.logger.error(f"下载文章失败: {str(e)}")
            return False, None
    
    def get_article_content(self, url):
        """获取文章内容并下载图片
        
        Args:
            url (str): 微信公众号文章URL
            
        Returns:
            tuple: (标题, Markdown内容) 或 (None, None)
        """
        try:
            # 获取页面内容
            response = requests.get(url, headers=self.headers, timeout=30)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                self.logger.error(f"请求失败，状态码: {response.status_code}")
                return None, None
                
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 获取文章标题
            title_element = soup.find('h1', class_='rich_media_title')
            if not title_element:
                title_element = soup.find('h1', id='activity-name')
            
            if not title_element:
                # 尝试从其他地方获取标题
                title_match = re.search(r'var msg_title = "([^"]+)"', response.text)
                if title_match:
                    title = title_match.group(1)
                else:
                    self.logger.error("无法找到文章标题")
                    return None, None
            else:
                title = title_element.get_text().strip()
            
            # 获取发布时间 - 尝试多种方式提取
            publish_time_str = ""
            
            
            # 方法0: 直接从HTML源码中搜索日期格式（最可靠的方法）
            # 尝试查找页面中任何位置的日期格式
            date_patterns = [
                r'(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{1,2})',  # 2025年03月05日 11:41
                r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})',       # 2025-03-05 11:41
            ]
            
            for pattern in date_patterns:
                # 在整个HTML源码中搜索
                matches = re.findall(pattern, response.text)
                if matches:
                    # 找到了日期，使用第一个匹配项
                    year, month, day, hour, minute = matches[0]
                    # 确保月日时分都是两位数
                    month = month.zfill(2) if len(month) == 1 else month
                    day = day.zfill(2) if len(day) == 1 else day
                    hour = hour.zfill(2) if len(hour) == 1 else hour
                    minute = minute.zfill(2) if len(minute) == 1 else minute
                    publish_time_str = f"{year}{month}{day}{hour}{minute}"
                    # self.logger.info(f"方法0从HTML源码中提取到发布时间: {matches[0]} -> {publish_time_str}")
                    break
            
            # 方法1: 直接查找publish_time元素
            if not publish_time_str:
                publish_time_element = soup.find('em', id='publish_time')
                if publish_time_element:
                    publish_time_text = publish_time_element.get_text().strip()
                    # self.logger.info(f"找到publish_time元素: {publish_time_text}")
                    if publish_time_text:
                        # 提取年月日时分
                        time_match = re.search(r'(\d{4})年(\d{2})月(\d{2})日\s+(\d{2}):(\d{2})', publish_time_text)
                        if time_match:
                            year, month, day, hour, minute = time_match.groups()
                            publish_time_str = f"{year}{month}{day}{hour}{minute}"
                            # self.logger.info(f"方法1提取到发布时间: {publish_time_text} -> {publish_time_str}")
            
            # 方法2: 查找meta_content_hide_info中的发布时间
            if not publish_time_str:
                meta_content = soup.find('span', id='meta_content_hide_info')
                if meta_content:
                    # self.logger.info(f"找到meta_content_hide_info元素")
                    publish_time_element = meta_content.find('em', id='publish_time')
                    if publish_time_element:
                        publish_time_text = publish_time_element.get_text().strip()
                        # self.logger.info(f"meta_content中找到publish_time元素: {publish_time_text}")
                        if publish_time_text:
                            time_match = re.search(r'(\d{4})年(\d{2})月(\d{2})日\s+(\d{2}):(\d{2})', publish_time_text)
                            if time_match:
                                year, month, day, hour, minute = time_match.groups()
                                publish_time_str = f"{year}{month}{day}{hour}{minute}"
                                # self.logger.info(f"方法2提取到发布时间: {publish_time_text} -> {publish_time_str}")
            
            # 方法3: 从JavaScript变量中提取
            if not publish_time_str:
                # 尝试多种可能的JavaScript变量名
                js_patterns = [
                    r'var\s+publish_time\s*=\s*"([^"]+)"',
                    r'var\s+ct\s*=\s*"([^"]+)"',
                    r'var\s+publish_time\s*=\s*\'([^\']+)\'',
                    r'publish_time\s*:\s*"([^"]+)"',
                    r'"publish_time"\s*:\s*"([^"]+)"',
                ]
                
                for pattern in js_patterns:
                    time_match = re.search(pattern, response.text)
                    if time_match:
                        publish_time_text = time_match.group(1)
                        # self.logger.info(f"从JavaScript变量中找到时间: {publish_time_text}")
                        
                        # 尝试多种日期格式
                        time_match1 = re.search(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})', publish_time_text)
                        time_match2 = re.search(r'(\d{4})年(\d{2})月(\d{2})日\s+(\d{2}):(\d{2})', publish_time_text)
                        
                        if time_match1:
                            year, month, day, hour, minute = time_match1.groups()
                            publish_time_str = f"{year}{month}{day}{hour}{minute}"
                            # self.logger.info(f"方法3提取到发布时间(格式1): {publish_time_text} -> {publish_time_str}")
                            break
                        elif time_match2:
                            year, month, day, hour, minute = time_match2.groups()
                            publish_time_str = f"{year}{month}{day}{hour}{minute}"
                            # self.logger.info(f"方法3提取到发布时间(格式2): {publish_time_text} -> {publish_time_str}")
                            break
            
            # 方法4: 查找任何包含日期格式的文本
            if not publish_time_str:
                # 先查找页面中所有可能包含日期的元素
                date_elements = soup.find_all(['span', 'em', 'div'], text=re.compile(r'\d{4}[年-]\d{1,2}[月-]\d{1,2}'))
                for element in date_elements:
                    element_text = element.get_text().strip()
                    # self.logger.info(f"找到可能包含日期的元素: {element_text}")
                    # 尝试多种日期格式
                    time_match1 = re.search(r'(\d{4})年(\d{2})月(\d{2})日\s+(\d{2}):(\d{2})', element_text)
                    time_match2 = re.search(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})', element_text)
                    
                    if time_match1:
                        year, month, day, hour, minute = time_match1.groups()
                        publish_time_str = f"{year}{month}{day}{hour}{minute}"
                        # self.logger.info(f"方法4提取到发布时间(格式1): {element_text} -> {publish_time_str}")
                        break
                    elif time_match2:
                        year, month, day, hour, minute = time_match2.groups()
                        publish_time_str = f"{year}{month}{day}{hour}{minute}"
                        # self.logger.info(f"方法4提取到发布时间(格式2): {element_text} -> {publish_time_str}")
                        break
            
            # 方法5: 从页面全文中搜索日期格式
            if not publish_time_str:
                all_text = soup.get_text()
                # 尝试多种日期格式
                time_match1 = re.search(r'(\d{4})年(\d{2})月(\d{2})日\s+(\d{2}):(\d{2})', all_text)
                time_match2 = re.search(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})', all_text)
                
                if time_match1:
                    year, month, day, hour, minute = time_match1.groups()
                    publish_time_str = f"{year}{month}{day}{hour}{minute}"
                    # self.logger.info(f"方法5提取到发布时间(格式1): {time_match1.group(0)} -> {publish_time_str}")
                elif time_match2:
                    year, month, day, hour, minute = time_match2.groups()
                    publish_time_str = f"{year}{month}{day}{hour}{minute}"
                    # self.logger.info(f"方法5提取到发布时间(格式2): {time_match2.group(0)} -> {publish_time_str}")
            
            # 如果所有方法都失败，使用文章URL中的参数或当前时间
            if not publish_time_str:
                # 尝试从URL中提取时间参数
                time_param_match = re.search(r'[?&]t=(\d+)', url)
                if time_param_match:
                    timestamp = int(time_param_match.group(1))
                    dt = datetime.fromtimestamp(timestamp)
                    publish_time_str = dt.strftime("%Y%m%d%H%M")
                    # self.logger.info(f"从URL参数提取到时间戳: {timestamp} -> {publish_time_str}")
                else:
                    # 使用当前时间 + 文章标题的哈希值的最后4位，确保不同文章有不同时间戳
                    now = datetime.now()
                    title_hash = abs(hash(title)) % 10000
                    base_time_str = now.strftime("%Y%m%d%H%M")
                    # 修改最后4位为标题哈希值
                    publish_time_str = f"{base_time_str[:-4]}{title_hash:04d}"
                    self.logger.warning(f"无法提取发布时间，使用当前时间+标题哈希: {publish_time_str}")
            
            # 设置当前文章标题和时间戳
            self.current_article_title = title
            self.current_publish_time = publish_time_str
            self.logger.info(f"[下载中]：{title}，时间戳：{publish_time_str}")
            
            # 获取文章内容 - 尝试多种可能的选择器
            content_element = soup.find('div', id='js_content')
            if not content_element:
                content_element = soup.find('div', class_='rich_media_content')
            
            if not content_element:
                content_element = soup.find('div', class_='js_underline_content')
                
            if not content_element:
                content_element = soup.find('div', class_=lambda c: c and ('rich_media_content' in c or 'js_underline_content' in c))
                
            if not content_element:
                self.logger.error("无法找到文章内容区域")
                return None, None
            
            # 预处理内容元素，保持原始结构
            self._preprocess_content(content_element)
            
            # 处理图片
            img_index = 0
            for img in content_element.find_all('img'):
                # 获取图片URL
                img_url = img.get('data-src') or img.get('src')
                if img_url:
                    img_url = urljoin(url, img_url)
                    
                    # 下载图片，使用序号
                    local_filename = self.download_image(img_url, img_index)
                    if local_filename:
                        # 更新图片链接为本地路径
                        img['src'] = f'./images/{local_filename}'
                        if 'data-src' in img.attrs:
                            del img['data-src']
                        img_index += 1
            
            # 转换为Markdown格式
            markdown_content = self._convert_to_markdown(title, content_element)
            
            return title, markdown_content
            
        except Exception as e:
            self.logger.error(f"获取文章内容失败: {str(e)}")
            traceback.print_exc()  # 打印完整的错误堆栈
            return None, None
    
    def _preprocess_content(self, content_element):
        """预处理内容元素，保持原始结构
        
        Args:
            content_element: BeautifulSoup对象，文章内容元素
        """
        # 处理所有的data-src属性
        for img in content_element.find_all('img'):
            if img.get('data-src') and not img.get('src'):
                img['src'] = img['data-src']
        
        # 处理所有的<br>标签，确保它们被正确解析为换行
        for br in content_element.find_all('br'):
            br.replace_with('\n')
        
        # 处理所有的<section>标签，确保它们被视为段落
        for section in content_element.find_all('section'):
            if not section.find(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'blockquote']):
                # 如果section中没有块级元素，将它视为段落
                section.name = 'p'
    
    def _convert_to_markdown(self, title, content_element):
        """将HTML内容转换为Markdown格式
        
        Args:
            title (str): 文章标题
            content_element: BeautifulSoup对象，文章内容元素
            
        Returns:
            str: Markdown格式的文章内容
        """
        markdown_content = f'# {title}\n\n'
        
        # 获取所有顶级元素
        top_elements = list(content_element.children)
        
        # 过滤掉纯空白文本节点
        top_elements = [el for el in top_elements if not (isinstance(el, str) and el.strip() == '')]
        
        # 处理每个顶级元素
        for element in top_elements:
            if isinstance(element, str):
                # 文本节点
                text = element.strip()
                if text:
                    markdown_content += text + '\n\n'
                continue
            
            # 处理图片节点
            if element.name == 'img':
                img_src = element.get('src')
                if img_src and img_src.startswith('./images/'):
                    markdown_content += f'![图片]({img_src})\n\n'
                continue
            
            # 处理段落
            if element.name == 'p':
                # 检查段落中是否只有图片
                images = element.find_all('img')
                if images and len(list(element.stripped_strings)) == 0:
                    # 段落中只有图片，单独处理每个图片
                    for img in images:
                        img_src = img.get('src')
                        if img_src and img_src.startswith('./images/'):
                            markdown_content += f'![图片]({img_src})\n\n'
                else:
                    # 处理段落中的文本和内联元素
                    p_content = self._process_inline_elements(element)
                    if p_content.strip():
                        markdown_content += p_content + '\n\n'
            
            # 处理标题
            elif element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                level = int(element.name[1])
                text = element.get_text().strip()
                if text:
                    markdown_content += f'{"#" * level} {text}\n\n'
            
            # 处理无序列表
            elif element.name == 'ul':
                list_content = self._process_list(element, ordered=False)
                if list_content:
                    markdown_content += list_content + '\n'
            
            # 处理有序列表
            elif element.name == 'ol':
                list_content = self._process_list(element, ordered=True)
                if list_content:
                    markdown_content += list_content + '\n'
            
            # 处理引用
            elif element.name == 'blockquote':
                blockquote_content = self._process_blockquote(element)
                if blockquote_content:
                    markdown_content += blockquote_content + '\n\n'
            
            # 处理代码块
            elif element.name == 'pre' or element.name == 'code':
                code = element.get_text().strip()
                if code:
                    markdown_content += f"```\n{code}\n```\n\n"
            
            # 处理div和section
            elif element.name in ['div', 'section']:
                # 递归处理div/section内容
                div_content = self._process_div_or_section(element)
                if div_content:
                    markdown_content += div_content
        
        return markdown_content.strip()
    
    def _process_inline_elements(self, element):
        """处理段落中的内联元素
        
        Args:
            element: BeautifulSoup对象，段落元素
            
        Returns:
            str: 处理后的Markdown文本
        """
        result = ""
        
        # 遍历所有子节点
        for child in element.children:
            if isinstance(child, str):
                # 文本节点
                result += child
            elif child.name == 'br':
                # 换行
                result += '\n'
            elif child.name == 'img':
                # 图片
                img_src = child.get('src')
                if img_src and img_src.startswith('./images/'):
                    result += f'![图片]({img_src})'
            elif child.name in ['strong', 'b']:
                # 加粗
                result += f"**{child.get_text().strip()}**"
            elif child.name in ['em', 'i']:
                # 斜体
                result += f"*{child.get_text().strip()}*"
            elif child.name == 'a':
                # 链接
                href = child.get('href', '')
                result += f"[{child.get_text().strip()}]({href})"
            elif child.name == 'code':
                # 行内代码
                result += f"`{child.get_text().strip()}`"
            elif child.name == 'span':
                # span通常用于样式，我们只提取文本
                result += child.get_text()
            else:
                # 其他元素，提取文本
                result += child.get_text()
        
        # 处理多个连续空格和换行
        result = re.sub(r'\s+', ' ', result)
        # 处理段落内的换行
        result = result.replace('\n', '\n\n')
        
        return result.strip()
    
    def _process_list(self, list_element, ordered=False):
        """处理列表元素
        
        Args:
            list_element: BeautifulSoup对象，列表元素
            ordered: 是否是有序列表
            
        Returns:
            str: 处理后的Markdown列表
        """
        result = ""
        
        for i, li in enumerate(list_element.find_all('li', recursive=False), 1):
            # 处理列表项中的图片
            has_img = False
            for img in li.find_all('img'):
                img_src = img.get('src')
                if img_src and img_src.startswith('./images/'):
                    # 计算嵌套层级
                    nesting_level = self._count_parents(list_element, ['ul', 'ol'])
                    result += f'{"    " * (nesting_level - 1)}![图片]({img_src})\n'
                    has_img = True
            
            # 处理列表项文本
            text = self._process_inline_elements(li)
            if text:
                prefix = f"{i}. " if ordered else "- "
                # 计算嵌套层级
                nesting_level = self._count_parents(list_element, ['ul', 'ol'])
                indent = "    " * (nesting_level - 1)
                result += f"{indent}{prefix}{text}\n"
            
            # 处理嵌套列表
            for nested_list in li.find_all(['ul', 'ol'], recursive=False):
                nested_content = self._process_list(
                    nested_list, 
                    ordered=nested_list.name == 'ol'
                )
                if nested_content:
                    result += nested_content
        
        return result
    
    def _count_parents(self, element, parent_tags):
        """计算元素的指定父元素数量
        
        Args:
            element: BeautifulSoup对象
            parent_tags: 要计数的父元素标签列表
            
        Returns:
            int: 父元素数量
        """
        count = 0
        parent = element.parent
        
        while parent:
            if parent.name in parent_tags:
                count += 1
            parent = parent.parent
            
        return count
    
    def _process_blockquote(self, blockquote):
        """处理引用元素
        
        Args:
            blockquote: BeautifulSoup对象，引用元素
            
        Returns:
            str: 处理后的Markdown引用
        """
        result = ""
        
        # 处理引用中的图片
        for img in blockquote.find_all('img'):
            img_src = img.get('src')
            if img_src and img_src.startswith('./images/'):
                result += f'> ![图片]({img_src})\n>\n'
        
        # 处理引用中的文本
        lines = []
        for p in blockquote.find_all(['p', 'div']):
            text = self._process_inline_elements(p)
            if text:
                lines.append(text)
        
        if not lines and blockquote.get_text().strip():
            # 如果没有找到段落但有文本，直接使用文本
            lines = [blockquote.get_text().strip()]
        
        # 添加引用标记
        if lines:
            result += '> ' + '\n> \n> '.join(lines)
        
        return result
    
    def _process_div_or_section(self, element):
        """递归处理div或section元素
        
        Args:
            element: BeautifulSoup对象，div或section元素
            
        Returns:
            str: 处理后的Markdown文本
        """
        result = ""
        
        # 检查是否只包含一个图片
        images = element.find_all('img', recursive=False)
        if len(images) == 1 and len(list(element.stripped_strings)) == 0:
            img = images[0]
            img_src = img.get('src')
            if img_src and img_src.startswith('./images/'):
                return f'![图片]({img_src})\n\n'
        
        # 处理子元素
        for child in element.children:
            if isinstance(child, str):
                # 文本节点
                text = child.strip()
                if text:
                    result += text + '\n\n'
            elif child.name == 'img':
                # 图片
                img_src = child.get('src')
                if img_src and img_src.startswith('./images/'):
                    result += f'![图片]({img_src})\n\n'
            elif child.name == 'p':
                # 段落
                p_content = self._process_inline_elements(child)
                if p_content:
                    result += p_content + '\n\n'
            elif child.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                # 标题
                level = int(child.name[1])
                text = child.get_text().strip()
                if text:
                    result += f'{"#" * level} {text}\n\n'
            elif child.name == 'ul':
                # 无序列表
                list_content = self._process_list(child, ordered=False)
                if list_content:
                    result += list_content + '\n'
            elif child.name == 'ol':
                # 有序列表
                list_content = self._process_list(child, ordered=True)
                if list_content:
                    result += list_content + '\n'
            elif child.name == 'blockquote':
                # 引用
                blockquote_content = self._process_blockquote(child)
                if blockquote_content:
                    result += blockquote_content + '\n\n'
            elif child.name in ['div', 'section']:
                # 递归处理嵌套的div/section
                div_content = self._process_div_or_section(child)
                if div_content:
                    result += div_content
        
        return result
    
    def download_image(self, img_url, index=None):
        """下载图片到指定目录
        
        Args:
            img_url (str): 图片URL
            index (int, optional): 图片索引，用于生成序号文件名
            
        Returns:
            str or None: 保存的图片文件名，下载失败则返回None
        """
        try:
            response = requests.get(img_url, stream=True, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                # 使用文章标题和序号生成文件名
                if self.current_article_title and index is not None:
                    # 从文章标题中提取合法的文件名部分
                    safe_title = re.sub(r'[<>:"/\\|?*]', '_', self.current_article_title)
                    # 如果有发布时间，添加到文件名前
                    if self.current_publish_time:
                        filename = f'{self.current_publish_time}-{safe_title}_{index:03d}.jpg'
                    else:
                        filename = f'{safe_title}_{index:03d}.jpg'
                else:
                    # 从URL中提取文件名，如果没有则使用时间戳
                    filename = os.path.basename(img_url.split('?')[0])
                    if not filename or len(filename) > 100 or not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        filename = f"img_{int(time.time() * 1000)}_{hash(img_url) % 10000}.jpg"
                
                # 确保文件名是合法的
                filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                
                # 保存图片
                file_path = os.path.join(self.images_dir, filename)
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                return filename
            else:
                self.logger.error(f"下载图片失败，状态码: {response.status_code}, URL: {img_url}")
                return None
        except Exception as e:
            self.logger.error(f"下载图片失败 {img_url}: {str(e)}")
            return None
    
    def save_to_markdown(self, title, content):
        """保存内容为Markdown文件
        
        Args:
            title (str): 文章标题
            content (str): Markdown格式的文章内容
            
        Returns:
            str or None: 保存的文件路径，保存失败则返回None
        """
        try:
            # 清理文件名中的非法字符
            safe_title = self._clean_filename(title)
            
            # 如果有发布时间，添加到文件名前
            if self.current_publish_time:
                filename = f"{self.current_publish_time}-{safe_title}.md"
            else:
                filename = f"{safe_title}.md"
                
            file_path = os.path.join(self.save_dir, filename)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f"[已保存]：{file_path}")
            return file_path
        except Exception as e:
            self.logger.error(f"保存Markdown文件失败: {str(e)}")
            return None
    
    def _clean_filename(self, filename):
        """清理文件名中的非法字符"""
        # 替换Windows文件名中不允许的字符
        invalid_chars = r'[\\/*?:"<>|]'
        return re.sub(invalid_chars, '_', filename)


class ArticleDownloadManager(QObject):
    """文章下载管理器，管理多线程下载"""
    
    # 定义信号
    download_status_changed = pyqtSignal(str, dict)  # 文章链接, 状态信息
    download_completed = pyqtSignal()  # 所有下载完成
    
    def __init__(self, save_dir="."):
        super().__init__()
        self.save_dir = save_dir
        self.download_queue = Queue()
        self.download_threads = []
        self.is_downloading = False
        self.download_results = {}
        self.max_threads = 3
        
    def add_article(self, article_info):
        """添加文章到下载队列
        
        Args:
            article_info: dict, 包含 'title', 'link' 字段
        """
        self.download_queue.put(article_info)
        self.download_results[article_info['link']] = {'status': '等待下载', 'file_path': None}
        self.download_status_changed.emit(article_info['link'], self.download_results[article_info['link']])
        
    def start_download(self):
        """开始下载队列中的文章"""
        if self.is_downloading:
            return
            
        self.is_downloading = True
        self.download_threads = []
        
        for _ in range(self.max_threads):
            thread = threading.Thread(target=self._download_worker)
            thread.daemon = True
            thread.start()
            self.download_threads.append(thread)
            
    def stop_download(self):
        """停止所有下载任务"""
        self.is_downloading = False
        
        # 清空下载队列
        while not self.download_queue.empty():
            try:
                article = self.download_queue.get_nowait()
                self.download_results[article['link']]['status'] = '已取消'
                self.download_status_changed.emit(article['link'], self.download_results[article['link']])
            except:
                pass
                
        # 等待所有线程结束
        for thread in self.download_threads:
            if thread.is_alive():
                thread.join(0.1)  # 非阻塞等待
            
        self.download_threads = []
        self.download_completed.emit()
        
    def _download_worker(self):
        """下载工作线程"""
        while self.is_downloading:
            try:
                article = self.download_queue.get(timeout=1)  # 等待1秒
            except Empty:
                # 如果队列为空，检查是否所有线程都已完成
                if self.download_queue.empty():
                    # 等待一段时间，确保所有状态都更新完成
                    time.sleep(0.5)
                    if self.is_downloading:
                        self.is_downloading = False
                        self.download_completed.emit()
                break
            except Exception as e:
                print(f"下载队列异常: {str(e)}")
                break
                
            try:
                # 更新状态为下载中
                self.download_results[article['link']]['status'] = '下载中...'
                self.download_status_changed.emit(article['link'], self.download_results[article['link']])
                
                # 创建下载器实例，直接使用主下载目录
                downloader = WeChatArticleDownloader(save_dir=self.save_dir)
                
                # 下载文章
                success, file_path = downloader.download_article(article['link'])
                
                # 更新下载状态
                if success:
                    self.download_results[article['link']] = {
                        'status': '下载成功',
                        'file_path': file_path
                    }
                else:
                    self.download_results[article['link']] = {
                        'status': '下载失败',
                        'file_path': None
                    }
                    
                self.download_status_changed.emit(article['link'], self.download_results[article['link']])
                    
            except Exception as e:
                self.download_results[article['link']] = {
                    'status': f'下载失败: {str(e)}',
                    'file_path': None
                }
                self.download_status_changed.emit(article['link'], self.download_results[article['link']])
                
            finally:
                self.download_queue.task_done()
                
    def get_article_status(self, article_link):
        """获取文章的下载状态"""
        return self.download_results.get(article_link, {'status': '未知', 'file_path': None})
