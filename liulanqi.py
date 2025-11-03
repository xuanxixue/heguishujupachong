import sys
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import re
import json
import logging
from threading import Thread
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtGui import *

# 必须在创建QApplication之前设置高DPI
if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    from googletrans import Translator
    SELENIUM_AVAILABLE = True
except ImportError as e:
    print(f"某些依赖未正确安装: {e}")
    SELENIUM_AVAILABLE = False

try:
    from docx import Document
    from docx.shared import Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    print("DOCX导出功能不可用，请安装python-docx: pip install python-docx")

class CrawlerThread(Thread):
    """爬虫线程，用于在后台执行爬取任务"""
    
    def __init__(self, crawler, url):
        super().__init__()
        self.crawler = crawler
        self.url = url
        self.running = True
    
    def run(self):
        """运行爬虫"""
        self.crawler.crawl_single_page(self.url)

class DocumentCrawler:
    """文档爬虫类"""
    
    def __init__(self, output_dir="crawled_data"):
        self.output_dir = output_dir
        self.crawled_data = []
        self.is_crawling = False
        self.current_task = None
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(output_dir, 'crawler.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # 初始化翻译器
        try:
            self.translator = Translator()
        except:
            self.translator = None
            self.logger.warning("翻译器初始化失败")
        
        # 初始化Selenium驱动
        self.driver = None
        if SELENIUM_AVAILABLE:
            self.setup_selenium()
    
    def setup_selenium(self):
        """设置Selenium WebDriver"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            # 尝试自动找到Chrome浏览器
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.logger.info("Selenium WebDriver初始化成功")
        except Exception as e:
            self.logger.warning(f"Selenium WebDriver初始化失败: {e}")
            # 尝试使用系统Chrome
            try:
                chrome_options.binary_location = self.find_chrome_path()
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.logger.info("使用系统Chrome路径初始化成功")
            except Exception as e2:
                self.logger.warning(f"使用系统Chrome路径也失败: {e2}")
                self.driver = None
    
    def find_chrome_path(self):
        """查找系统Chrome安装路径"""
        possible_paths = [
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None
    
    def is_valid_url(self, url):
        """检查URL是否有效"""
        try:
            parsed = urlparse(url)
            return (parsed.netloc and 
                    parsed.scheme in ['http', 'https'] and
                    not any(ext in url.lower() for ext in ['.pdf', '.jpg', '.png', '.gif', '.zip', '.exe']))
        except:
            return False
    
    def can_crawl(self, url):
        """检查是否可以爬取该URL"""
        if not self.is_valid_url(url):
            return False, "URL格式无效"
        
        # 检查robots.txt
        try:
            robots_url = urljoin(url, '/robots.txt')
            response = requests.get(robots_url, timeout=5)
            if response.status_code == 200:
                # 简单的robots.txt检查
                if 'Disallow: /' in response.text:
                    return False, "robots.txt禁止爬取"
        except:
            pass  # 如果无法获取robots.txt，我们仍然尝试爬取
        
        return True, "可以爬取"
    
    def clean_text(self, text):
        """清理和预处理文本"""
        if not text:
            return ""
        # 移除多余的空格和换行
        text = re.sub(r'\s+', ' ', text)
        # 移除特殊字符但保留基本标点
        text = re.sub(r'[^\w\s\.\,\!\?\-\(\)\:\;]', '', text)
        # 移除网址
        text = re.sub(r'http\S+', '', text)
        return text.strip()
    
    def extract_text_content(self, soup):
        """从BeautifulSoup对象中提取文本内容"""
        # 移除脚本和样式标签
        for script in soup(["script", "style"]):
            script.decompose()
        
        # 提取主要文本内容
        text_parts = []
        
        # 优先提取标题
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            text_parts.append(heading.get_text().strip())
        
        # 提取段落文本
        for paragraph in soup.find_all('p'):
            text = paragraph.get_text().strip()
            if len(text) > 20:  # 只保留较长的段落
                text_parts.append(text)
        
        # 提取列表项
        for list_item in soup.find_all('li'):
            text = list_item.get_text().strip()
            if len(text) > 10:
                text_parts.append(text)
        
        # 合并所有文本
        full_text = ' '.join(text_parts)
        return self.clean_text(full_text)
    
    def crawl_with_requests(self, url):
        """使用requests库爬取页面"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 检测编码
            if response.encoding.lower() != 'utf-8':
                response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.content, 'lxml')
            return soup, True
        except Exception as e:
            self.logger.warning(f"使用requests爬取 {url} 失败: {e}")
            return None, False
    
    def crawl_with_selenium(self, url):
        """使用Selenium爬取JavaScript渲染的页面"""
        if not self.driver:
            return None, False
        
        try:
            self.driver.get(url)
            # 等待页面加载
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 获取页面源码
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'lxml')
            return soup, True
        except Exception as e:
            self.logger.warning(f"使用Selenium爬取 {url} 失败: {e}")
            return None, False
    
    def crawl_single_page(self, url):
        """爬取单个页面"""
        self.is_crawling = True
        self.logger.info(f"正在爬取: {url}")
        
        # 首先尝试使用requests（更快）
        soup, success = self.crawl_with_requests(url)
        
        # 如果失败，尝试使用Selenium
        if not success and self.driver:
            soup, success = self.crawl_with_selenium(url)
        
        if not success:
            self.is_crawling = False
            return False, "爬取失败"
        
        # 提取文本内容
        text_content = self.extract_text_content(soup)
        
        if not text_content or len(text_content) < 100:
            self.is_crawling = False
            return False, "页面内容过少或无文本内容"
        
        # 保存数据
        title = url.split('/')[-1] or "无标题"
        if len(text_content) > 50:
            title = text_content[:50] + "..."
        
        data_item = {
            'url': url,
            'title': title,
            'content': text_content,
            'length': len(text_content),
            'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        self.crawled_data.append(data_item)
        
        # 保存到文件
        self.save_data()
        
        self.is_crawling = False
        return True, f"成功爬取，获取 {len(text_content)} 个字符"
    
    def translate_text(self, text, dest_lang='zh-cn'):
        """翻译文本"""
        try:
            if self.translator:
                translated = self.translator.translate(text, dest=dest_lang)
                return translated.text
            else:
                return "翻译功能不可用"
        except Exception as e:
            self.logger.error(f"翻译失败: {e}")
            return f"翻译失败: {str(e)}"
    
    def save_data(self):
        """保存爬取的数据"""
        try:
            # 保存为JSON
            json_path = os.path.join(self.output_dir, 'crawled_data.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(self.crawled_data, f, ensure_ascii=False, indent=2)
            
            # 保存为纯文本（用于训练AI）
            text_path = os.path.join(self.output_dir, 'training_data.txt')
            with open(text_path, 'w', encoding='utf-8') as f:
                for item in self.crawled_data:
                    f.write(f"URL: {item['url']}\n")
                    f.write(f"标题: {item['title']}\n")
                    f.write(f"内容: {item['content']}\n")
                    f.write("\n" + "="*80 + "\n\n")
            
            self.logger.info(f"数据已保存到: {self.output_dir}")
        except Exception as e:
            self.logger.error(f"保存数据失败: {e}")
    
    def export_to_docx(self, filepath=None):
        """导出数据为DOCX文档"""
        if not DOCX_AVAILABLE:
            return False, "DOCX导出功能不可用，请安装python-docx库"
        
        if not self.crawled_data:
            return False, "没有数据可导出"
        
        try:
            # 如果没有指定文件路径，使用默认路径
            if not filepath:
                filepath = os.path.join(self.output_dir, 'crawled_data.docx')
            
            # 创建文档
            doc = Document()
            
            # 添加标题
            title = doc.add_heading('网页数据采集报告', 0)
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # 添加基本信息
            doc.add_paragraph(f"采集时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            doc.add_paragraph(f"采集页面数量: {len(self.crawled_data)}")
            doc.add_paragraph("")
            
            # 添加每个页面的内容
            for i, data in enumerate(self.crawled_data, 1):
                # 添加页面标题
                doc.add_heading(f"页面 {i}: {data['title']}", level=1)
                
                # 添加URL
                url_para = doc.add_paragraph("URL: ")
                url_para.add_run(data['url']).bold = True
                
                # 添加采集时间
                doc.add_paragraph(f"采集时间: {data['crawl_time']}")
                
                # 添加内容
                doc.add_heading("内容", level=2)
                content_para = doc.add_paragraph(data['content'])
                
                # 添加分隔线
                if i < len(self.crawled_data):
                    doc.add_paragraph("")
                    doc.add_paragraph("=" * 50)
                    doc.add_paragraph("")
            
            # 保存文档
            doc.save(filepath)
            self.logger.info(f"DOCX文档已保存到: {filepath}")
            return True, f"DOCX文档已保存到: {filepath}"
            
        except Exception as e:
            self.logger.error(f"导出DOCX失败: {e}")
            return False, f"导出DOCX失败: {str(e)}"

class ModernButton(QPushButton):
    """现代化按钮样式"""
    def __init__(self, text, icon_name=None, parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(36)
        self.setCursor(Qt.PointingHandCursor)
        
        # 基础样式
        self.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
            QPushButton:pressed {
                background-color: #2D6CA2;
            }
            QPushButton:disabled {
                background-color: #B0B0B0;
                color: #E0E0E0;
            }
        """)

class BrowserWithCrawler(QMainWindow):
    """现代化浏览器爬虫工具"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI数据采集浏览器")
        self.setGeometry(100, 100, 1600, 900)
        
        # 设置应用样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F5F7FA;
            }
            QWidget {
                background-color: #F5F7FA;
            }
            QLabel {
                color: #2C3E50;
                font-weight: 600;
            }
            QLineEdit {
                padding: 10px 12px;
                border: 2px solid #E1E8ED;
                border-radius: 6px;
                background-color: white;
                font-size: 13px;
                selection-background-color: #4A90E2;
            }
            QLineEdit:focus {
                border-color: #4A90E2;
            }
            QListWidget {
                border: 2px solid #E1E8ED;
                border-radius: 6px;
                background-color: white;
                alternate-background-color: #F8F9FA;
                font-size: 13px;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #E1E8ED;
            }
            QListWidget::item:selected {
                background-color: #E3F2FD;
                color: #1976D2;
                border: none;
            }
            QListWidget::item:hover {
                background-color: #F5F5F5;
            }
            QTextEdit {
                border: 2px solid #E1E8ED;
                border-radius: 6px;
                background-color: white;
                padding: 12px;
                font-size: 13px;
                line-height: 1.5;
            }
            QSplitter::handle {
                background-color: #D1D9E0;
                width: 4px;
                border-radius: 2px;
            }
            QTabWidget::pane {
                border: 2px solid #E1E8ED;
                border-radius: 8px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #F0F4F8;
                border: 1px solid #E1E8ED;
                border-bottom: none;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
                color: #64748B;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #4A90E2;
                border-bottom: 2px solid #4A90E2;
            }
            QTabBar::tab:hover:!selected {
                background-color: #E8F4FD;
                color: #357ABD;
            }
            QGroupBox {
                border: 2px solid #E1E8ED;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                color: #2C3E50;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
            }
            QProgressBar {
                border: 2px solid #E1E8ED;
                border-radius: 6px;
                text-align: center;
                background-color: #F0F4F8;
            }
            QProgressBar::chunk {
                background-color: #4A90E2;
                border-radius: 4px;
            }
        """)
        
        # 初始化爬虫
        self.crawler = DocumentCrawler()
        self.crawl_thread = None
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        
        # 创建浏览器组件 - 必须先创建
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("https://www.google.com"))
        
        # 创建顶部工具栏
        self.create_top_toolbar(main_layout)
        
        # 创建主内容区域
        self.create_main_content(main_layout)
        
        # 创建底部状态栏
        self.create_status_bar(main_layout)
        
        # 连接信号
        self.browser.urlChanged.connect(self.update_url)
        self.browser.loadFinished.connect(self.update_title)
        
        # 初始更新
        self.update_url(self.browser.url())
        self.update_data_list()
        
        # 显示Selenium状态
        if not SELENIUM_AVAILABLE:
            self.status_label.setText("⚠️ Selenium不可用，部分网站可能无法爬取")
        
        # 显示DOCX状态
        if not DOCX_AVAILABLE:
            self.status_label.setText("⚠️ DOCX导出功能不可用，请安装python-docx")
    
    def create_top_toolbar(self, parent_layout):
        """创建顶部工具栏"""
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)
        
        # 导航按钮
        self.back_btn = ModernButton("←")
        self.back_btn.setFixedSize(40, 36)
        self.back_btn.setToolTip("后退")
        self.back_btn.clicked.connect(self.browser.back)
        
        self.forward_btn = ModernButton("→")
        self.forward_btn.setFixedSize(40, 36)
        self.forward_btn.setToolTip("前进")
        self.forward_btn.clicked.connect(self.browser.forward)
        
        self.reload_btn = ModernButton("↻")
        self.reload_btn.setFixedSize(40, 36)
        self.reload_btn.setToolTip("刷新")
        self.reload_btn.clicked.connect(self.browser.reload)
        
        # 地址栏
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("输入网址并按下回车...")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        
        # 爬虫控制按钮
        self.check_btn = ModernButton("检查可爬取性")
        self.check_btn.clicked.connect(self.check_crawlability)
        self.check_btn.setToolTip("检查当前页面是否可以爬取")
        
        self.crawl_btn = ModernButton("爬取页面")
        self.crawl_btn.clicked.connect(self.crawl_current_page)
        self.crawl_btn.setToolTip("爬取当前页面内容")
        self.crawl_btn.setStyleSheet("""
            QPushButton {
                background-color: #27AE60;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #219653;
            }
            QPushButton:pressed {
                background-color: #1E874B;
            }
        """)
        
        # 添加到工具栏
        toolbar_layout.addWidget(self.back_btn)
        toolbar_layout.addWidget(self.forward_btn)
        toolbar_layout.addWidget(self.reload_btn)
        toolbar_layout.addWidget(self.url_bar, 1)
        toolbar_layout.addWidget(self.check_btn)
        toolbar_layout.addWidget(self.crawl_btn)
        
        parent_layout.addWidget(toolbar_widget)
    
    def create_main_content(self, parent_layout):
        """创建主内容区域"""
        # 创建水平分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧 - 浏览器
        browser_container = QWidget()
        browser_layout = QVBoxLayout(browser_container)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(0)
        
        # 添加浏览器到左侧容器
        browser_layout.addWidget(self.browser)
        
        # 右侧 - 数据面板
        data_container = QWidget()
        data_layout = QVBoxLayout(data_container)
        data_layout.setContentsMargins(0, 0, 0, 0)
        data_layout.setSpacing(12)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        
        # 数据列表选项卡
        data_list_tab = QWidget()
        data_list_layout = QVBoxLayout(data_list_tab)
        data_list_layout.setContentsMargins(12, 12, 12, 12)
        data_list_layout.setSpacing(12)
        
        # 数据列表标题
        data_list_label = QLabel("已爬取的数据")
        data_list_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2C3E50;")
        
        # 数据列表
        self.data_list = QListWidget()
        self.data_list.itemClicked.connect(self.show_data_content)
        self.data_list.setAlternatingRowColors(True)
        
        # 数据操作按钮
        data_buttons_layout = QHBoxLayout()
        self.save_btn = ModernButton("保存数据")
        self.save_btn.clicked.connect(self.save_crawled_data)
        
        self.clear_btn = ModernButton("清空数据")
        self.clear_btn.clicked.connect(self.clear_crawled_data)
        
        self.export_btn = ModernButton("导出训练数据")
        self.export_btn.clicked.connect(self.export_training_data)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #9B59B6;
                color: white;
            }
            QPushButton:hover {
                background-color: #8E44AD;
            }
        """)
        
        self.export_docx_btn = ModernButton("导出DOCX")
        self.export_docx_btn.clicked.connect(self.export_to_docx)
        self.export_docx_btn.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
                color: white;
            }
            QPushButton:hover {
                background-color: #C0392B;
            }
        """)
        if not DOCX_AVAILABLE:
            self.export_docx_btn.setEnabled(False)
            self.export_docx_btn.setToolTip("DOCX导出功能不可用，请安装python-docx")
        
        data_buttons_layout.addWidget(self.save_btn)
        data_buttons_layout.addWidget(self.clear_btn)
        data_buttons_layout.addWidget(self.export_btn)
        data_buttons_layout.addWidget(self.export_docx_btn)
        data_buttons_layout.addStretch()
        
        # 添加到数据列表选项卡
        data_list_layout.addWidget(data_list_label)
        data_list_layout.addWidget(self.data_list, 1)
        data_list_layout.addLayout(data_buttons_layout)
        
        # 数据预览选项卡
        data_preview_tab = QWidget()
        data_preview_layout = QVBoxLayout(data_preview_tab)
        data_preview_layout.setContentsMargins(12, 12, 12, 12)
        data_preview_layout.setSpacing(12)
        
        # 预览标题
        preview_label = QLabel("数据预览")
        preview_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2C3E50;")
        
        # 翻译工具栏
        translate_toolbar = QHBoxLayout()
        translate_label = QLabel("翻译:")
        translate_label.setStyleSheet("font-weight: 600;")
        
        self.translate_en_btn = ModernButton("英译中")
        self.translate_en_btn.clicked.connect(lambda: self.translate_content('zh-cn'))
        
        self.translate_zh_btn = ModernButton("中译英")
        self.translate_zh_btn.clicked.connect(lambda: self.translate_content('en'))
        
        translate_toolbar.addWidget(translate_label)
        translate_toolbar.addWidget(self.translate_en_btn)
        translate_toolbar.addWidget(self.translate_zh_btn)
        translate_toolbar.addStretch()
        
        # 数据内容显示
        self.data_content = QTextEdit()
        self.data_content.setReadOnly(True)
        
        # 添加到预览选项卡
        data_preview_layout.addWidget(preview_label)
        data_preview_layout.addLayout(translate_toolbar)
        data_preview_layout.addWidget(self.data_content, 1)
        
        # 添加选项卡
        self.tab_widget.addTab(data_list_tab, "📋 数据列表")
        self.tab_widget.addTab(data_preview_tab, "👁️ 数据预览")
        
        # 添加到数据容器
        data_layout.addWidget(self.tab_widget)
        
        # 添加到分割器
        splitter.addWidget(browser_container)
        splitter.addWidget(data_container)
        splitter.setSizes([700, 500])
        
        parent_layout.addWidget(splitter, 1)
    
    def create_status_bar(self, parent_layout):
        """创建底部状态栏"""
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.setSpacing(8)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #E8F4FD; 
                padding: 8px 12px;
                border-radius: 6px;
                color: #2C3E50;
                font-weight: 500;
                border: 1px solid #BBDEFB;
            }
        """)
        
        # 数据统计
        self.data_stats = QLabel("数据: 0 条")
        self.data_stats.setStyleSheet("""
            QLabel {
                background-color: #E8F5E8; 
                padding: 8px 12px;
                border-radius: 6px;
                color: #2C3E50;
                font-weight: 500;
                border: 1px solid #C8E6C9;
            }
        """)
        
        status_layout.addWidget(self.status_label, 1)
        status_layout.addWidget(self.data_stats)
        
        parent_layout.addWidget(status_widget)
    
    def navigate_to_url(self):
        """导航到地址栏中的URL"""
        url = self.url_bar.text().strip()
        if not url:
            return
            
        if not url.startswith('http'):
            url = 'https://' + url
            
        # 添加加载中状态
        self.status_label.setText("🔄 加载中...")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #FFF3CD; 
                padding: 8px 12px;
                border-radius: 6px;
                color: #856404;
                font-weight: 500;
                border: 1px solid #FFECB5;
            }
        """)
        
        self.browser.setUrl(QUrl(url))
    
    def update_url(self, q):
        """更新地址栏显示"""
        self.url_bar.setText(q.toString())
    
    def update_title(self):
        """更新窗口标题"""
        title = self.browser.page().title()
        self.setWindowTitle(f"{title} - AI数据采集浏览器")
        self.status_label.setText("✅ 页面加载完成")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #E8F5E8; 
                padding: 8px 12px;
                border-radius: 6px;
                color: #2C3E50;
                font-weight: 500;
                border: 1px solid #C8E6C9;
            }
        """)
    
    def check_crawlability(self):
        """检查当前页面是否可以爬取"""
        current_url = self.browser.url().toString()
        if not current_url:
            self.status_label.setText("❌ 无当前URL")
            return
        
        can_crawl, message = self.crawler.can_crawl(current_url)
        if can_crawl:
            self.status_label.setText("✅ " + message)
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #E8F5E8; 
                    padding: 8px 12px;
                    border-radius: 6px;
                    color: #2C3E50;
                    font-weight: 500;
                    border: 1px solid #C8E6C9;
                }
            """)
        else:
            self.status_label.setText("❌ " + message)
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #FFEBEE; 
                    padding: 8px 12px;
                    border-radius: 6px;
                    color: #2C3E50;
                    font-weight: 500;
                    border: 1px solid #FFCDD2;
                }
            """)
    
    def crawl_current_page(self):
        """爬取当前页面"""
        if self.crawler.is_crawling:
            self.status_label.setText("⏳ 正在爬取中，请等待...")
            return
        
        current_url = self.browser.url().toString()
        if not current_url:
            self.status_label.setText("❌ 无当前URL")
            return
        
        # 检查是否可以爬取
        can_crawl, message = self.crawler.can_crawl(current_url)
        if not can_crawl:
            self.status_label.setText("❌ " + message)
            return
        
        # 在后台线程中执行爬取
        self.crawl_thread = CrawlerThread(self.crawler, current_url)
        self.crawl_thread.start()
        
        self.status_label.setText("🔄 正在爬取页面...")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #E3F2FD; 
                padding: 8px 12px;
                border-radius: 6px;
                color: #2C3E50;
                font-weight: 500;
                border: 1px solid #BBDEFB;
            }
        """)
        
        # 禁用爬取按钮
        self.crawl_btn.setEnabled(False)
        
        # 启动定时器检查爬取状态
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_crawl_status)
        self.check_timer.start(500)  # 每500毫秒检查一次
    
    def check_crawl_status(self):
        """检查爬取状态"""
        if not self.crawler.is_crawling and self.crawl_thread and not self.crawl_thread.is_alive():
            # 爬取完成
            self.check_timer.stop()
            self.crawl_btn.setEnabled(True)
            
            # 更新数据列表
            self.update_data_list()
            
            # 显示最新爬取的数据
            if self.crawler.crawled_data:
                latest_data = self.crawler.crawled_data[-1]
                self.data_content.setText(latest_data['content'])
                self.status_label.setText(f"✅ 爬取完成: {latest_data['title']}")
                self.status_label.setStyleSheet("""
                    QLabel {
                        background-color: #E8F5E8; 
                        padding: 8px 12px;
                        border-radius: 6px;
                        color: #2C3E50;
                        font-weight: 500;
                        border: 1px solid #C8E6C9;
                    }
                """)
            else:
                self.status_label.setText("⚠️ 爬取完成但未获取到数据")
                self.status_label.setStyleSheet("""
                    QLabel {
                        background-color: #FFF3CD; 
                        padding: 8px 12px;
                        border-radius: 6px;
                        color: #856404;
                        font-weight: 500;
                        border: 1px solid #FFECB5;
                    }
                """)
    
    def update_data_list(self):
        """更新数据列表"""
        self.data_list.clear()
        for i, data in enumerate(self.crawler.crawled_data):
            item = QListWidgetItem(f"{i+1}. {data['title']} ({data['length']} 字符)")
            item.setData(Qt.UserRole, i)  # 存储索引
            self.data_list.addItem(item)
        
        # 更新数据统计
        self.data_stats.setText(f"数据: {len(self.crawler.crawled_data)} 条")
        
        # 如果有数据，自动选择最后一项
        if self.crawler.crawled_data:
            self.data_list.setCurrentRow(len(self.crawler.crawled_data) - 1)
            self.show_data_content(self.data_list.currentItem())
    
    def show_data_content(self, item):
        """显示选中数据的内容"""
        if not item:
            return
            
        index = item.data(Qt.UserRole)
        if index < len(self.crawler.crawled_data):
            data = self.crawler.crawled_data[index]
            self.data_content.setText(data['content'])
    
    def translate_content(self, dest_lang):
        """翻译当前内容"""
        text = self.data_content.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "警告", "没有内容可翻译")
            return
        
        # 显示翻译中状态
        original_text = text
        self.data_content.setText("🔄 翻译中...")
        self.data_content.repaint()
        
        # 在后台执行翻译
        def do_translate():
            try:
                translated = self.crawler.translate_text(original_text, dest_lang)
                return translated
            except Exception as e:
                return f"❌ 翻译失败: {str(e)}"
        
        # 使用QTimer模拟异步操作
        def update_translation():
            translated = do_translate()
            self.data_content.setText(translated)
        
        QTimer.singleShot(100, update_translation)
    
    def save_crawled_data(self):
        """保存爬取的数据"""
        if not self.crawler.crawled_data:
            QMessageBox.information(self, "提示", "没有数据可保存")
            return
        
        try:
            # 保存为JSON
            json_path = os.path.join(self.crawler.output_dir, 'crawled_data.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(self.crawler.crawled_data, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "成功", f"数据已保存到 {json_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存数据失败: {str(e)}")
    
    def export_training_data(self):
        """导出训练数据"""
        if not self.crawler.crawled_data:
            QMessageBox.information(self, "提示", "没有数据可导出")
            return
        
        try:
            # 保存为纯文本（用于训练AI）
            text_path = os.path.join(self.crawler.output_dir, 'training_data.txt')
            with open(text_path, 'w', encoding='utf-8') as f:
                for item in self.crawler.crawled_data:
                    f.write(f"URL: {item['url']}\n")
                    f.write(f"标题: {item['title']}\n")
                    f.write(f"内容: {item['content']}\n")
                    f.write("\n" + "="*80 + "\n\n")
            
            QMessageBox.information(self, "成功", f"训练数据已导出到 {text_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出训练数据失败: {str(e)}")
    
    def export_to_docx(self):
        """导出数据为DOCX文档"""
        if not self.crawler.crawled_data:
            QMessageBox.information(self, "提示", "没有数据可导出")
            return
        
        # 选择保存路径
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存DOCX文档", 
            os.path.join(self.crawler.output_dir, "crawled_data.docx"),
            "Word文档 (*.docx)"
        )
        
        if not filepath:
            return
        
        # 显示导出中状态
        self.status_label.setText("🔄 正在导出DOCX文档...")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #E3F2FD; 
                padding: 8px 12px;
                border-radius: 6px;
                color: #2C3E50;
                font-weight: 500;
                border: 1px solid #BBDEFB;
            }
        """)
        
        # 在后台执行导出
        def do_export():
            return self.crawler.export_to_docx(filepath)
        
        # 使用QTimer模拟异步操作
        def update_export_status():
            success, message = do_export()
            if success:
                self.status_label.setText("✅ " + message)
                self.status_label.setStyleSheet("""
                    QLabel {
                        background-color: #E8F5E8; 
                        padding: 8px 12px;
                        border-radius: 6px;
                        color: #2C3E50;
                        font-weight: 500;
                        border: 1px solid #C8E6C9;
                    }
                """)
                QMessageBox.information(self, "成功", message)
            else:
                self.status_label.setText("❌ " + message)
                self.status_label.setStyleSheet("""
                    QLabel {
                        background-color: #FFEBEE; 
                        padding: 8px 12px;
                        border-radius: 6px;
                        color: #2C3E50;
                        font-weight: 500;
                        border: 1px solid #FFCDD2;
                    }
                """)
                QMessageBox.critical(self, "错误", message)
        
        QTimer.singleShot(100, update_export_status)
    
    def clear_crawled_data(self):
        """清空爬取的数据"""
        if not self.crawler.crawled_data:
            return
        
        reply = QMessageBox.question(self, "确认", "确定要清空所有爬取的数据吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.crawler.crawled_data.clear()
            self.update_data_list()
            self.data_content.clear()
            self.status_label.setText("数据已清空")

def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("AI数据采集浏览器")
    app.setApplicationVersion("2.0")
    
    # 设置应用字体
    font = QFont()
    font.setFamily("Microsoft YaHei")
    font.setPointSize(10)
    app.setFont(font)
    
    window = BrowserWithCrawler()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()