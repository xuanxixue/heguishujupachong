import sys
import os
import json
import urllib.robotparser
from urllib.parse import urlparse, urljoin
from datetime import datetime
import time
import re
import logging
from threading import Thread
from PyQt5.QtCore import QUrl, Qt, QTimer, pyqtSignal, QSize, QStandardPaths
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QLineEdit, QToolBar, QLabel,
    QTabWidget, QStatusBar, QAction, QFileDialog, QMessageBox,
    QSizePolicy, QListWidget, QListWidgetItem, QTextEdit, QSplitter,
    QGroupBox, QProgressBar, QMenu, QDialog, QDialogButtonBox,
    QListWidget, QTreeWidget, QTreeWidgetItem, QHeaderView, QCheckBox,
    # 添加新的导入
    QDockWidget, QTextBrowser
)
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPalette, QColor, QKeySequence
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile, QWebEngineDownloadItem, QWebEngineSettings
import requests
from bs4 import BeautifulSoup

# 导入拆分的模块
from web_engine import CustomWebEnginePage
from download_manager import DownloadManager
from history_manager import HistoryManager
from bookmarks_manager import BookmarksManager
from settings_dialog import SettingsDialog
from crawler_worker import CrawlerWorker
from ai_module import AIChatDialog, AISummaryDialog  # 新增AI模块
from utils import SELENIUM_AVAILABLE, DOCX_AVAILABLE
# 添加 PluginManager 的导入
from plugin_manager import PluginManager
# 添加更新管理器导入
from update_manager import UpdateManager

class ModernBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("道衍AI浏览器 - 智能合规爬虫版")
        self.resize(1400, 900)
        
        # 初始化组件
        self.crawler = CrawlerWorker()
        self.download_manager = DownloadManager(self)
        self.history_manager = HistoryManager(self)
        self.bookmarks_manager = BookmarksManager(self)
        self.settings_dialog = SettingsDialog(self)
        self.plugins = {}  # 插件存储
        
        # 开发者工具相关
        self.dev_tools_visible = False
        self.dev_tools_dock = None
        self.dev_tools_view = None
        
        # 下载设置
        self.download_path = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        self.ask_before_download = True
        
        # 标签页会话文件
        self.session_file = "session.json"

        self.setup_ui()
        self.setup_downloads()
        self.load_session()
        self.load_plugins()  # 加载插件

    def setup_downloads(self):
        """设置下载处理器"""
        profile = QWebEngineProfile.defaultProfile()
        profile.downloadRequested.connect(self.on_download_requested)

    def on_download_requested(self, download):
        """处理下载请求"""
        if self.ask_before_download:
            path, _ = QFileDialog.getSaveFileName(
                self, "保存文件", 
                os.path.join(self.download_path, download.downloadFileName())
            )
            if path:
                download.setPath(path)
                download.accept()
                self.download_manager.add_download(download)
                self.download_manager.show()
            else:
                download.cancel()
        else:
            download.setPath(os.path.join(self.download_path, download.downloadFileName()))
            download.accept()
            self.download_manager.add_download(download)
            self.download_manager.show()

    def setup_ui(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f0f0; }
            QLineEdit {
                padding: 10px;
                border: 2px solid #ccc;
                border-radius: 20px;
                font-size: 14px;
            }
            QPushButton {
                background-color: white;
                border: 1px solid #ddd;
                padding: 8px 12px;
                border-radius: 18px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #f9f9f9; border-color: #aaa; }
            QTabBar::tab {
                background-color: white;
                color: #333;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background-color: #e6f7ff;
                font-weight: bold;
            }
            QToolBar {
                background-color: white;
                border-bottom: 1px solid #ddd;
                spacing: 10px;
                padding: 8px;
            }
            QLabel#status {
                color: #555;
                padding: 4px 8px;
                background: #eee;
                border-radius: 10px;
            }
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 8px;
                background: white;
            }
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 8px;
                background: white;
            }
            QGroupBox {
                border: 2px solid #ddd;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                background: white;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 左侧：浏览器主体
        browser_container = QWidget()
        browser_layout = QVBoxLayout(browser_container)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        self.create_toolbar(browser_layout)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        browser_layout.addWidget(self.tab_widget)
        # 注意：这里不再默认添加标签页，而是通过会话恢复

        # 右侧：爬虫数据面板
        self.data_panel = self.create_data_panel()

        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(browser_container)
        splitter.addWidget(self.data_panel)
        splitter.setSizes([900, 500])
        main_layout.addWidget(splitter)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("准备就绪", objectName="status")
        self.status_bar.addPermanentWidget(self.status_label)

        # 创建菜单栏
        self.create_menubar()

        # 创建开发者工具停靠窗口
        self.create_dev_tools()
        
        # 创建公告显示区域
        self.create_announcement_panel()
        
        # 创建安装包接收区域
        self.create_update_panel()

    def create_menubar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        new_tab_action = QAction("新建标签页", self)
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.triggered.connect(lambda: self.add_new_tab(QUrl("https://www.baidu.com")))
        
        new_tab_action = QAction("新建标签页", self)
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.triggered.connect(lambda: self.add_new_tab(QUrl("https://www.baidu.com")))
        
        new_window_action = QAction("新建窗口", self)
        new_window_action.setShortcut("Ctrl+N")
        new_window_action.triggered.connect(self.new_window)
        
        quit_action = QAction("退出", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        
        file_menu.addAction(new_tab_action)
        file_menu.addAction(new_window_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")
        
        cut_action = QAction("剪切", self)
        cut_action.setShortcut("Ctrl+X")
        cut_action.triggered.connect(self.cut)
        
        copy_action = QAction("复制", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self.copy)
        
        paste_action = QAction("粘贴", self)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(self.paste)
        
        edit_menu.addAction(cut_action)
        edit_menu.addAction(copy_action)
        edit_menu.addAction(paste_action)

        # 查看菜单
        view_menu = menubar.addMenu("查看")
        
        zoom_in_action = QAction("放大", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(self.zoom_in)
        
        zoom_out_action = QAction("缩小", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(self.zoom_out)
        
        zoom_reset_action = QAction("重置缩放", self)
        zoom_reset_action.setShortcut("Ctrl+0")
        zoom_reset_action.triggered.connect(self.zoom_reset)
        
        # 添加开发者工具选项
        dev_tools_action = QAction("开发者工具", self)
        dev_tools_action.setShortcut("F12")
        dev_tools_action.setCheckable(True)
        dev_tools_action.setChecked(self.dev_tools_visible)
        dev_tools_action.triggered.connect(self.toggle_dev_tools)
        
        view_menu.addAction(zoom_in_action)
        view_menu.addAction(zoom_out_action)
        view_menu.addAction(zoom_reset_action)
        view_menu.addSeparator()
        view_menu.addAction(dev_tools_action)

        # 书签菜单
        bookmarks_menu = menubar.addMenu("书签")
        
        add_bookmark_action = QAction("添加书签", self)
        add_bookmark_action.setShortcut("Ctrl+D")
        add_bookmark_action.triggered.connect(self.add_bookmark)
        
        bookmarks_manager_action = QAction("书签管理器", self)
        bookmarks_manager_action.setShortcut("Ctrl+Shift+O")
        bookmarks_manager_action.triggered.connect(self.bookmarks_manager.show)
        
        bookmarks_menu.addAction(add_bookmark_action)
        bookmarks_menu.addAction(bookmarks_manager_action)

        # 工具菜单
        tools_menu = menubar.addMenu("工具")
        
        downloads_action = QAction("下载管理器", self)
        downloads_action.setShortcut("Ctrl+J")
        downloads_action.triggered.connect(self.download_manager.show)
        
        history_action = QAction("历史记录", self)
        history_action.setShortcut("Ctrl+H")
        history_action.triggered.connect(self.history_manager.show)
        
        translate_action = QAction("页面翻译", self)
        translate_action.setShortcut("Ctrl+Shift+T")
        translate_action.triggered.connect(self.translate_page)
        
        # 新增AI相关菜单项
        ai_menu = menubar.addMenu("AI 功能")
        ai_chat_action = QAction("AI 聊天", self)
        ai_chat_action.setShortcut("Ctrl+Shift+I")
        ai_chat_action.triggered.connect(self.open_ai_chat)
        ai_summary_action = QAction("AI 网页总结", self)
        ai_summary_action.setShortcut("Ctrl+Shift+S")
        ai_summary_action.triggered.connect(self.summarize_current_page)
        ai_menu.addAction(ai_chat_action)
        ai_menu.addAction(ai_summary_action)
        
        # 插件菜单
        plugins_menu = menubar.addMenu("插件")
        manage_plugins_action = QAction("插件管理", self)
        manage_plugins_action.triggered.connect(self.open_plugin_manager)
        plugins_menu.addAction(manage_plugins_action)
        
        settings_action = QAction("设置", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.settings_dialog.exec_)
        
        tools_menu.addAction(downloads_action)
        tools_menu.addAction(history_action)
        tools_menu.addAction(translate_action)
        tools_menu.addSeparator()
        tools_menu.addAction(settings_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        # 添加更新和公告功能
        update_action = QAction("检查更新", self)
        update_action.triggered.connect(self.open_update_manager)
        help_menu.addAction(update_action)
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        
        help_menu.addAction(about_action)

    def create_toolbar(self, parent_layout):
        toolbar = QToolBar()
        toolbar.setMovable(False)

        self.back_btn = QPushButton("⏪")
        self.forward_btn = QPushButton("⏩")
        self.reload_btn = QPushButton("🔄")
        self.home_btn = QPushButton("🏠")
        self.downloads_btn = QPushButton("📥")
        self.history_btn = QPushButton("📚")
        self.bookmarks_btn = QPushButton("🔖")
        
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("输入网址或关键词（自动百度搜索）")
        
        self.crawl_btn = QPushButton("🕷️ 抓取当前页")
        self.translate_btn = QPushButton("🌐 翻译")
        # 新增AI功能按钮
        self.ai_chat_btn = QPushButton("💬 AI聊天")
        self.ai_summary_btn = QPushButton("📝 AI总结")
        # 新增插件按钮
        self.plugins_btn = QPushButton("🧩 插件")
        new_tab_btn = QPushButton("+")

        # 连接信号
        self.back_btn.clicked.connect(self.on_back_clicked)
        self.forward_btn.clicked.connect(self.on_forward_clicked)
        self.reload_btn.clicked.connect(self.on_reload_clicked)
        self.home_btn.clicked.connect(self.go_home)
        self.downloads_btn.clicked.connect(self.download_manager.show)
        self.history_btn.clicked.connect(self.history_manager.show)
        self.bookmarks_btn.clicked.connect(self.bookmarks_manager.show)
        self.url_bar.returnPressed.connect(self.on_go_or_search)
        self.crawl_btn.clicked.connect(self.start_crawl)
        self.translate_btn.clicked.connect(self.translate_page)
        # 连接AI功能按钮
        self.ai_chat_btn.clicked.connect(self.open_ai_chat)
        self.ai_summary_btn.clicked.connect(self.summarize_current_page)
        # 连接插件按钮
        self.plugins_btn.clicked.connect(self.open_plugin_manager)
        new_tab_btn.clicked.connect(lambda: self.add_new_tab(QUrl("https://www.baidu.com")))

        # 添加到工具栏
        toolbar.addWidget(self.back_btn)
        toolbar.addWidget(self.forward_btn)
        toolbar.addWidget(self.reload_btn)
        toolbar.addWidget(self.home_btn)
        toolbar.addSeparator()
        toolbar.addWidget(self.downloads_btn)
        toolbar.addWidget(self.history_btn)
        toolbar.addWidget(self.bookmarks_btn)
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        toolbar.addWidget(spacer)
        
        toolbar.addWidget(self.url_bar)
        toolbar.addWidget(self.crawl_btn)
        toolbar.addWidget(self.translate_btn)
        # 添加AI功能按钮到工具栏
        toolbar.addWidget(self.ai_chat_btn)
        toolbar.addWidget(self.ai_summary_btn)
        # 添加插件按钮到工具栏
        toolbar.addWidget(self.plugins_btn)
        toolbar.addWidget(new_tab_btn)
        parent_layout.addWidget(toolbar)

    def add_new_tab(self, url, title="新标签页"):
        browser = QWebEngineView()
        
        # 创建自定义页面，并传递主窗口引用
        page = CustomWebEnginePage(browser, self)
        browser.setPage(page)
        
        # 设置更真实的用户代理
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        browser.page().profile().setHttpUserAgent(user_agent)
        
        # 启用所有必要的Web引擎功能
        settings = browser.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
        settings.setAttribute(QWebEngineSettings.ScrollAnimatorEnabled, True)
        settings.setAttribute(QWebEngineSettings.AutoLoadImages, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        settings.setAttribute(QWebEngineSettings.AllowWindowActivationFromJavaScript, True)
        settings.setAttribute(QWebEngineSettings.HyperlinkAuditingEnabled, True)
        settings.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)
        # 启用开发者工具
        settings.setAttribute(QWebEngineSettings.AutoLoadIconsForPage, True)
        settings.setAttribute(QWebEngineSettings.TouchIconsEnabled, True)

        browser.load(url)
        browser.titleChanged.connect(lambda t: self.update_tab_title(browser, t))
        browser.loadFinished.connect(lambda ok: self.on_load_finished(ok, browser))
        browser.urlChanged.connect(lambda q: self.on_url_changed(browser, q))

        index = self.tab_widget.addTab(browser, title)
        self.tab_widget.setCurrentIndex(index)
        self.save_session()  # 保存会话
        return browser

    def update_tab_title(self, browser, title):
        index = self.tab_widget.indexOf(browser)
        if index != -1:
            truncated = title[:20] + "..." if len(title) > 20 else title
            self.tab_widget.setTabText(index, truncated)

    def on_load_finished(self, success, browser):
        if success:
            self.status_label.setText("页面加载完成")
            # 添加到历史记录
            self.history_manager.add_history(browser.title(), browser.url().toString())
        else:
            self.status_label.setText("加载失败")
        self.update_navigation_buttons()

    def on_url_changed(self, browser, url):
        if browser == self.tab_widget.currentWidget():
            self.url_bar.setText(url.toString())
        self.save_session()  # URL改变时保存会话

    def close_tab(self, index):
        if self.tab_widget.count() > 1:
            widget = self.tab_widget.widget(index)
            widget.deleteLater()
            self.tab_widget.removeTab(index)
        else:
            self.tab_widget.clear()
            self.add_new_tab(QUrl("https://www.baidu.com"))
        self.save_session()  # 关闭标签页时保存会话

    def on_tab_changed(self, index):
        if index == -1: return
        browser = self.tab_widget.currentWidget()
        if isinstance(browser, QWebEngineView):
            self.url_bar.setText(browser.url().toString())
            self.update_navigation_buttons()
            # 更新开发者工具
            if self.dev_tools_visible and self.dev_tools_view:
                self.dev_tools_view.page().setInspectedPage(browser.page())

    def on_back_clicked(self):
        browser = self.tab_widget.currentWidget()
        if isinstance(browser, QWebEngineView): browser.back()

    def on_forward_clicked(self):
        browser = self.tab_widget.currentWidget()
        if isinstance(browser, QWebEngineView): browser.forward()

    def on_reload_clicked(self):
        browser = self.tab_widget.currentWidget()
        if isinstance(browser, QWebEngineView):
            browser.reload()

    def go_home(self):
        browser = self.tab_widget.currentWidget()
        if isinstance(browser, QWebEngineView):
            browser.load(QUrl("https://www.baidu.com"))

    def on_go_or_search(self):
        text = self.url_bar.text().strip()
        if not text: return

        if text.startswith(("http://", "https://")):
            url = QUrl(text)
        elif '.' in text:
            url = QUrl("https://" + text)
        else:
            encoded = requests.utils.quote(text)
            url = QUrl(f"https://www.baidu.com/s?wd={encoded}")

        browser = self.tab_widget.currentWidget()
        if isinstance(browser, QWebEngineView): 
            browser.load(url)

    def start_crawl(self):
        browser = self.tab_widget.currentWidget()
        if not isinstance(browser, QWebEngineView): return

        current_url = browser.url().toString()

        if not self.crawler.can_fetch(current_url):
            reply = QMessageBox.question(
                self, "风险提示",
                f"⚠️ robots.txt 不允许爬取该网站。\n是否继续？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No: return

        self.status_label.setText("🔍 正在抓取页面...")
        QTimer.singleShot(100, lambda: self._do_crawl_in_thread(current_url))

    def _do_crawl_in_thread(self, url):
        success, msg = self.crawler.crawl_single_page(url)
        self.status_label.setText(f"{'✅' if success else '❌'} {msg}")
        self.update_data_list()

    def create_data_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)

        group = QGroupBox("爬取数据管理")
        group_layout = QVBoxLayout()

        # 创建标签页控件用于切换数据和教程
        tab_widget = QTabWidget()
        
        # 数据面板
        data_widget = QWidget()
        data_layout = QVBoxLayout(data_widget)
        
        # 数据列表
        self.data_list = QListWidget()
        self.data_list.itemClicked.connect(self.show_data_detail)

        # 数据预览
        self.data_preview = QTextEdit()
        self.data_preview.setReadOnly(True)

        # 操作按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("💾 保存数据")
        clear_btn = QPushButton("🗑️ 清空")
        export_txt = QPushButton("📤 导出训练集")
        export_docx = QPushButton("📄 导出DOCX")
        export_docx.setEnabled(DOCX_AVAILABLE)

        save_btn.clicked.connect(self.save_all_data)
        clear_btn.clicked.connect(self.clear_all_data)
        export_txt.clicked.connect(self.export_training_data)
        export_docx.clicked.connect(self.export_as_docx)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(export_txt)
        btn_layout.addWidget(export_docx)

        data_layout.addWidget(QLabel("已抓取页面"))
        data_layout.addWidget(self.data_list)
        data_layout.addWidget(QLabel("内容预览"))
        data_layout.addWidget(self.data_preview)
        data_layout.addLayout(btn_layout)
        
        # 教程面板
        tutorial_widget = QWidget()
        tutorial_layout = QVBoxLayout(tutorial_widget)
        
        self.tutorial_list = QListWidget()
        self.tutorial_list.addItems([
            "软件使用基础教程",
            "插件开发入门",
            "AI功能使用指南",
            "爬虫功能详解",
            "数据导出与管理"
        ])
        self.tutorial_list.itemClicked.connect(self.show_tutorial)
        
        self.tutorial_preview = QTextEdit()
        self.tutorial_preview.setReadOnly(True)
        
        tutorial_layout.addWidget(QLabel("教程列表"))
        tutorial_layout.addWidget(self.tutorial_list)
        tutorial_layout.addWidget(QLabel("教程内容"))
        tutorial_layout.addWidget(self.tutorial_preview)
        
        # 添加标签页
        tab_widget.addTab(data_widget, "爬取数据")
        tab_widget.addTab(tutorial_widget, "使用教程")

        group_layout.addWidget(tab_widget)
        group.setLayout(group_layout)
        layout.addWidget(group)
        return panel

    def update_data_list(self):
        self.data_list.clear()
        for i, d in enumerate(self.crawler.crawled_data):
            item = QListWidgetItem(f"{i+1}. {d['title']} ({d['word_count']}字)")
            item.setData(Qt.UserRole, i)
            self.data_list.addItem(item)

    def show_data_detail(self, item):
        idx = item.data(Qt.UserRole)
        data = self.crawler.crawled_data[idx]
        content = (
            f"📌 标题: {data['title']}\n"
            f"🔗 URL: {data['url']}\n"
            f"📅 时间: {data['timestamp']}\n"
            f"📝 字数: {data['word_count']}, 字符: {data['char_count']}\n"
            f"🔗 内链:{data['internal_links']} 外链:{data['external_links']}\n\n"
            f"{data['full_content']}"
        )
        self.data_preview.setText(content)

    def save_all_data(self):
        path = os.path.join(self.crawler.output_dir, "crawled_data.json")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.crawler.crawled_data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "成功", f"数据已保存到：\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "失败", str(e))

    def clear_all_data(self):
        if QMessageBox.question(self, "确认", "清空所有爬取数据？") == QMessageBox.Yes:
            self.crawler.crawled_data.clear()
            self.data_list.clear()
            self.data_preview.clear()

    def export_training_data(self):
        path = os.path.join(self.crawler.output_dir, "training_data.txt")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                for d in self.crawler.crawled_data:
                    f.write(f"URL: {d['url']}\n")
                    f.write(f"标题: {d['title']}\n")
                    f.write(f"内容:\n{d['full_content']}\n")
                    f.write("\n" + "="*80 + "\n\n")
            QMessageBox.information(self, "成功", f"训练数据已生成：\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "失败", str(e))

    def export_as_docx(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存DOCX", "", "Word文件 (*.docx)")
        if not path: return
        success, msg = self.crawler.export_to_docx(path)
        QMessageBox.information(self, "结果", msg)

    def update_navigation_buttons(self):
        browser = self.tab_widget.currentWidget()
        if isinstance(browser, QWebEngineView):
            self.back_btn.setEnabled(browser.history().canGoBack())
            self.forward_btn.setEnabled(browser.history().canGoForward())

    # 新增的浏览器功能
    def new_window(self):
        """新建浏览器窗口"""
        new_browser = ModernBrowser()
        new_browser.show()

    def cut(self):
        """剪切"""
        browser = self.tab_widget.currentWidget()
        if isinstance(browser, QWebEngineView):
            browser.triggerPageAction(QWebEnginePage.Cut)

    def copy(self):
        """复制"""
        browser = self.tab_widget.currentWidget()
        if isinstance(browser, QWebEngineView):
            browser.triggerPageAction(QWebEnginePage.Copy)

    def paste(self):
        """粘贴"""
        browser = self.tab_widget.currentWidget()
        if isinstance(browser, QWebEngineView):
            browser.triggerPageAction(QWebEnginePage.Paste)

    def zoom_in(self):
        """放大页面"""
        browser = self.tab_widget.currentWidget()
        if isinstance(browser, QWebEngineView):
            current_zoom = browser.zoomFactor()
            browser.setZoomFactor(min(current_zoom + 0.1, 3.0))

    def zoom_out(self):
        """缩小页面"""
        browser = self.tab_widget.currentWidget()
        if isinstance(browser, QWebEngineView):
            current_zoom = browser.zoomFactor()
            browser.setZoomFactor(max(current_zoom - 0.1, 0.25))

    def zoom_reset(self):
        """重置缩放"""
        browser = self.tab_widget.currentWidget()
        if isinstance(browser, QWebEngineView):
            browser.setZoomFactor(1.0)

    def add_bookmark(self):
        """添加书签"""
        self.bookmarks_manager.add_bookmark()

    def translate_page(self):
        """翻译当前页面"""
        browser = self.tab_widget.currentWidget()
        if not isinstance(browser, QWebEngineView): 
            return
            
        current_url = browser.url().toString()
        # 使用百度翻译API进行页面翻译
        # 构造百度翻译URL
        baidu_translate_url = f"https://fanyi.baidu.com/transpage?query={current_url}&from=auto&to=zh&source=url&render=1"
        
        # 在新标签页中打开翻译结果
        self.add_new_tab(QUrl(baidu_translate_url), f"翻译: {browser.title()}")

    def show_about(self):
        """显示关于对话框"""
        about_text = """
        <h2>道衍AI浏览器</h2>
        <p><b>版本：</b>2.0 专业版</p>
        <p><b>功能特性：</b></p>
        <ul>
            <li>智能网页爬虫和数据提取</li>
            <li>完整的下载管理系统</li>
            <li>浏览历史记录</li>
            <li>书签管理</li>
            <li>多标签页浏览</li>
            <li>AI训练数据导出</li>
            <li>合规robots.txt检查</li>
            <li>AI聊天助手</li>
            <li>AI网页总结</li>
            <li>开发者工具 (F12)</li>
        </ul>
        <p><b>技术支持：</b>基于PyQt5和QWebEngine构建</p>
        """
        QMessageBox.about(self, "关于道衍AI浏览器", about_text)

    # 新增AI功能
    def open_ai_chat(self):
        """打开AI聊天对话框"""
        # 检查API设置
        if not self.settings_dialog.ai_api_url.text() or not self.settings_dialog.ai_api_key.text():
            QMessageBox.warning(self, "配置缺失", "请先在设置中配置AI API URL和密钥")
            self.settings_dialog.exec_()
            return
            
        api_settings = {
            "api_url": self.settings_dialog.ai_api_url.text(),
            "api_key": self.settings_dialog.ai_api_key.text(),
            "model": self.settings_dialog.ai_model.currentText()
        }
        
        chat_dialog = AIChatDialog(api_settings, self)
        chat_dialog.exec_()

    def summarize_current_page(self):
        """总结当前页面"""
        # 检查API设置
        if not self.settings_dialog.ai_api_url.text() or not self.settings_dialog.ai_api_key.text():
            QMessageBox.warning(self, "配置缺失", "请先在设置中配置AI API URL和密钥")
            self.settings_dialog.exec_()
            return
            
        browser = self.tab_widget.currentWidget()
        if not isinstance(browser, QWebEngineView):
            return
            
        # 获取页面标题和内容
        page_title = browser.title()
        
        # 通过JavaScript获取页面文本内容
        browser.page().toPlainText(lambda content: self._show_summary_dialog(content, page_title))
        
    def _show_summary_dialog(self, page_content, page_title):
        """显示总结对话框"""
        api_settings = {
            "api_url": self.settings_dialog.ai_api_url.text(),
            "api_key": self.settings_dialog.ai_api_key.text(),
            "model": self.settings_dialog.ai_model.currentText()
        }
        
        summary_dialog = AISummaryDialog(api_settings, page_content, page_title, self)
        summary_dialog.exec_()

    def open_plugin_manager(self):
        """打开插件管理器"""
        plugin_manager = PluginManager(self.plugins, self)
        if plugin_manager.exec_() == QDialog.Accepted:
            # 重新加载插件
            self.load_plugins()

    def load_plugins(self):
        """加载插件"""
        plugins_dir = "plugins"
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)
            return

        # 清除现有插件
        self.plugins.clear()

        # 遍历插件目录
        for plugin_name in os.listdir(plugins_dir):
            plugin_path = os.path.join(plugins_dir, plugin_name)
            if os.path.isdir(plugin_path):
                try:
                    # 尝试加载插件
                    plugin_module = __import__(f"plugins.{plugin_name}.main", fromlist=['Plugin'])
                    plugin_class = getattr(plugin_module, 'Plugin')
                    plugin_instance = plugin_class(self)
                    self.plugins[plugin_name] = {
                        'instance': plugin_instance,
                        'module': plugin_module,
                        'path': plugin_path
                    }
                    # 初始化插件
                    plugin_instance.init()
                except Exception as e:
                    print(f"加载插件 {plugin_name} 失败: {e}")

    def save_session(self):
        """保存当前会话（标签页状态）"""
        session_data = []
        for i in range(self.tab_widget.count()):
            browser = self.tab_widget.widget(i)
            if isinstance(browser, QWebEngineView):
                url = browser.url().toString()
                title = self.tab_widget.tabText(i)
                session_data.append({
                    "url": url,
                    "title": title
                })
        
        try:
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存会话失败: {e}")

    def load_session(self):
        """加载之前保存的会话"""
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                
                # 根据保存的会话恢复标签页
                for tab_data in session_data:
                    url = QUrl(tab_data["url"])
                    title = tab_data["title"]
                    self.add_new_tab(url, title)
                    
                # 如果没有保存的会话，则添加默认标签页
                if not session_data:
                    self.add_new_tab(QUrl("https://www.baidu.com"), "首页")
            except Exception as e:
                print(f"加载会话失败: {e}")
                # 出错时添加默认标签页
                self.add_new_tab(QUrl("https://www.baidu.com"), "首页")
        else:
            # 没有会话文件时添加默认标签页
            self.add_new_tab(QUrl("https://www.baidu.com"), "首页")

    def closeEvent(self, event):
        """窗口关闭事件，保存会话"""
        self.save_session()
        event.accept()

    def show_tutorial(self, item):
        """显示选中的教程内容"""
        tutorial_title = item.text()
        tutorial_content = self.get_tutorial_content(tutorial_title)
        self.tutorial_preview.setText(tutorial_content)

    def get_tutorial_content(self, title):
        """获取教程内容"""
        tutorials = {
            "软件使用基础教程": """软件使用基础教程

欢迎使用道衍AI浏览器！本教程将带您快速上手这款强大的AI浏览器。

1. 浏览器基本操作
   - 地址栏输入网址或搜索关键词
   - 使用工具栏按钮进行前进、后退、刷新等操作
   - 通过标签页管理多个页面

2. 爬虫功能使用
   - 点击"🕷️ 抓取当前页"按钮抓取当前页面内容
   - 抓取的数据会显示在右侧"爬取数据"面板中
   - 可以保存、导出或清空抓取的数据

3. AI功能介绍
   - 使用"💬 AI聊天"与AI助手对话
   - 使用"📝 AI总结"对当前页面进行总结
   - 在设置中配置AI API相关信息

4. 数据管理
   - 所有抓取的数据可以在右侧面板中查看
   - 支持导出为JSON、TXT和DOCX格式
   - 可以随时清空数据重新开始

如果您有任何疑问，请查看其他教程或联系技术支持。""",
            
            "插件开发入门": """插件开发入门

道衍AI浏览器支持插件扩展，您可以开发自己的插件来增强浏览器功能。

1. 插件结构
   插件需要放置在程序目录下的"plugins"文件夹中，每个插件为一个独立文件夹。
   
   插件基本结构如下：
   plugins/
     your_plugin/
       plugin.json    # 插件信息文件（可选）
       main.py        # 插件主程序文件

2. plugin.json 文件格式
   {
       "name": "插件名称",
       "version": "1.0.0",
       "description": "插件描述",
       "author": "作者",
       "main": "main.py"
   }

3. main.py 文件编写
   插件主文件需要包含一个Plugin类，示例代码：
   
   from PyQt5.QtWidgets import QAction, QMessageBox

   class Plugin:
       def __init__(self, browser):
           self.browser = browser  # 浏览器主窗口实例
       
       def init(self):
           # 插件初始化，可以在这里添加菜单项等
           action = QAction("我的插件功能", self.browser)
           action.triggered.connect(self.do_something)
           
           # 添加到工具菜单
           tools_menu = None
           for action in self.browser.menuBar().actions():
               if action.text() == "工具":
                   tools_menu = action.menu()
                   break
           if tools_menu:
               tools_menu.addAction(action)
       
       def do_something(self):
           # 插件功能实现
           QMessageBox.information(self.browser, "插件", "插件功能执行！")
       
       def cleanup(self):
           # 插件清理工作
           pass

4. 插件管理
   - 通过"插件"菜单中的"插件管理"可以添加、移除插件
   - 添加插件后需要点击"重新加载"使插件生效
   - 支持.zip格式的插件包和.py单文件插件

5. 开发建议
   - 插件应尽量避免影响浏览器主程序运行
   - 插件功能应与浏览器核心功能互补
   - 建议提供详细的插件说明文档""",

            "AI功能使用指南": """AI功能使用指南

道衍AI浏览器集成了强大的AI功能，可以帮助您更好地处理网页内容。

1. AI聊天功能
   - 点击工具栏上的"💬 AI聊天"按钮打开聊天窗口
   - 在输入框中输入您的问题或指令
   - 点击"发送"或按回车键发送消息
   - AI助手会回复相关内容

2. AI网页总结
   - 在想要总结的网页上点击"📝 AI总结"按钮
   - 系统会自动提取页面内容并生成总结
   - 总结内容会在弹窗中显示

3. AI设置
   - 在"设置"对话框中配置AI相关参数
   - 需要填写API URL和API密钥
   - 可以选择不同的AI模型

4. 支持的AI服务
   - OpenAI GPT系列模型
   - Claude系列模型
   - DeepSeek系列模型
   - Kimi系列模型
   - 通义千问系列模型
   - 零一万物系列模型
   - 其他兼容OpenAI API格式的服务

5. 使用注意事项
   - 请确保网络连接正常
   - 注意API调用次数限制
   - 保护好您的API密钥信息
   - 长文本可能会增加处理时间""",

            "爬虫功能详解": """爬虫功能详解

道衍AI浏览器内置了强大的网页爬虫功能，可以抓取并分析网页内容。

1. 基本爬虫操作
   - 访问目标网页
   - 点击"🕷️ 抓取当前页"按钮
   - 等待抓取完成，结果会显示在右侧数据面板

2. 爬虫技术特点
   - 支持静态页面解析（使用requests+BeautifulSoup）
   - 支持动态页面渲染（使用Selenium，需要安装相应依赖）
   - 自动遵守robots.txt协议
   - 智能内容提取算法

3. 数据字段说明
   - 标题：网页标题
   - URL：网页地址
   - 内容预览：提取的主要文本内容
   - 字数统计：内容字数和字符数
   - 链接统计：内链和外链数量
   - 图片链接：页面中的图片地址

4. 数据导出功能
   - JSON格式：完整结构化数据
   - TXT格式：纯文本训练数据
   - DOCX格式：Word文档（需要安装python-docx）

5. 爬虫设置建议
   - 合理控制爬取频率，避免对目标服务器造成压力
   - 注意遵守网站的使用条款
   - 对于重要数据及时备份
   - 可以根据需要调整内容提取规则""",

            "数据导出与管理": """数据导出与管理

道衍AI浏览器提供了多种数据导出和管理方式，方便您处理抓取的数据。

1. 数据查看
   - 在右侧"爬取数据"面板中查看已抓取的内容
   - 点击列表项可在下方预览详细内容
   - 支持实时查看数据统计信息

2. 数据保存
   - 点击"💾 保存数据"按钮将数据保存为JSON格式
   - 数据默认保存在"crawled_data"文件夹中
   - 包含完整的结构化信息

3. 数据导出
   - "📤 导出训练集"：导出为TXT格式，适合用于AI训练
   - "📄 导出DOCX"：导出为Word文档格式（需要安装python-docx）
   - 导出文件同样保存在"crawled_data"文件夹中

4. 数据清空
   - 点击"🗑️ 清空"按钮可以清空当前所有抓取数据
   - 此操作不可逆，请谨慎操作

5. 数据安全
   - 建议定期备份重要数据
   - 导出的文件可以用于其他AI项目训练
   - 注意保护敏感数据，避免泄露

6. 数据分析建议
   - 可以使用Python pandas等工具进一步分析数据
   - 结合AI功能对数据进行深度处理
   - 建立自己的垂直领域数据集"""
        }
        
        return tutorials.get(title, "教程内容暂未提供，请选择其他教程。")

    # 开发者工具相关方法
    def create_dev_tools(self):
        """创建开发者工具停靠窗口"""
        self.dev_tools_dock = QDockWidget("开发者工具", self)
        self.dev_tools_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.dev_tools_dock.hide()
        
        self.dev_tools_view = QWebEngineView()
        self.dev_tools_dock.setWidget(self.dev_tools_view)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dev_tools_dock)
        
        # 连接停靠窗口关闭事件
        self.dev_tools_dock.visibilityChanged.connect(self.on_dev_tools_visibility_changed)

    def toggle_dev_tools(self):
        """切换开发者工具显示/隐藏"""
        self.dev_tools_visible = not self.dev_tools_visible
        if self.dev_tools_visible:
            self.open_dev_tools()
        else:
            self.dev_tools_dock.hide()

    def open_dev_tools(self):
        """打开开发者工具"""
        current_browser = self.tab_widget.currentWidget()
        if isinstance(current_browser, QWebEngineView):
            # 设置被检查的页面
            self.dev_tools_view.page().setInspectedPage(current_browser.page())
            self.dev_tools_dock.show()
            self.dev_tools_visible = True
        else:
            QMessageBox.warning(self, "警告", "当前没有可检查的页面")

    def on_dev_tools_visibility_changed(self, visible):
        """开发者工具可见性改变时的处理"""
        self.dev_tools_visible = visible
        # 更新菜单项的选中状态
        for action in self.menuBar().actions():
            if action.text() == "查看":
                for sub_action in action.menu().actions():
                    if sub_action.text() == "开发者工具":
                        sub_action.setChecked(visible)

    def open_update_manager(self):
        """打开更新管理器"""
        update_manager = UpdateManager(self)
        update_manager.exec_()
        
    # 添加公告显示区域
    def create_announcement_panel(self):
        """创建公告显示区域"""
        self.announcement_dock = QDockWidget("公告", self)
        self.announcement_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        
        # 创建公告显示区域
        announcement_widget = QWidget()
        announcement_layout = QVBoxLayout(announcement_widget)
        
        # 添加标题栏和关闭按钮
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("公告"))
        title_layout.addStretch()
        
        self.close_announcement_btn = QPushButton("×")
        self.close_announcement_btn.setFixedSize(20, 20)
        self.close_announcement_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 2px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff6666;
                color: white;
            }
        """)
        self.close_announcement_btn.clicked.connect(self.close_announcement_panel)
        title_layout.addWidget(self.close_announcement_btn)
        
        # 创建类似邮箱的界面布局
        email_layout = QHBoxLayout()
        
        # 左侧公告列表
        self.announcement_list = QListWidget()
        self.announcement_list.setMaximumWidth(200)
        self.announcement_list.itemClicked.connect(self.load_selected_announcement)
        
        # 右侧公告内容显示
        self.announcement_display = QTextBrowser()
        self.announcement_display.setOpenExternalLinks(True)
        
        email_layout.addWidget(self.announcement_list)
        email_layout.addWidget(self.announcement_display)
        
        # 设置默认公告内容
        default_announcement = """
        <h3>欢迎使用道衍AI浏览器</h3>
        <p>当前版本：2.0 专业版</p>
        <p><b>系统公告：</b></p>
        <ul>
            <li>智能网页爬虫和数据提取</li>
            <li>完整的下载管理系统</li>
            <li>浏览历史记录</li>
            <li>书签管理</li>
            <li>多标签页浏览</li>
            <li>AI训练数据导出</li>
            <li>合规robots.txt检查</li>
            <li>AI聊天助手</li>
            <li>AI网页总结</li>
        </ul>
        <p>请通过"帮助"菜单中的"检查更新"功能获取最新公告和更新。</p>
        """
        self.announcement_display.setHtml(default_announcement)
        
        announcement_layout.addLayout(title_layout)
        announcement_layout.addLayout(email_layout)
        self.announcement_dock.setWidget(announcement_widget)
        
        # 将公告面板停靠在底部
        self.addDockWidget(Qt.BottomDockWidgetArea, self.announcement_dock)
        
        # 初始化公告列表
        self.init_announcement_list()
        
    def init_announcement_list(self):
        """初始化公告列表"""
        # 添加默认系统公告
        system_item = QListWidgetItem("系统公告")
        system_item.setData(Qt.UserRole, {
            "type": "system",
            "title": "系统公告",
            "content": """
            <h3>欢迎使用道衍AI浏览器</h3>
            <p>当前版本：2.0 专业版</p>
            <p><b>系统公告：</b></p>
            <ul>
                <li>智能网页爬虫和数据提取</li>
                <li>完整的下载管理系统</li>
                <li>浏览历史记录</li>
                <li>书签管理</li>
                <li>多标签页浏览</li>
                <li>AI训练数据导出</li>
                <li>合规robots.txt检查</li>
                <li>AI聊天助手</li>
                <li>AI网页总结</li>
            </ul>
            <p>请通过"帮助"菜单中的"检查更新"功能获取最新公告和更新。</p>
            """
        })
        self.announcement_list.addItem(system_item)
        
        # 添加示例局域网公告
        lan_item = QListWidgetItem("局域网公告")
        lan_item.setData(Qt.UserRole, {
            "type": "lan",
            "title": "局域网公告",
            "content": """
            <h3>局域网功能说明</h3>
            <p><b>局域网公告：</b></p>
            <ul>
                <li>支持局域网内设备发现</li>
                <li>可接收局域网内其他设备发送的公告</li>
                <li>支持P2P通信功能</li>
            </ul>
            <p>公告将自动从局域网服务器加载。</p>
            """
        })
        self.announcement_list.addItem(lan_item)
        
        # 设置默认选中第一个公告
        self.announcement_list.setCurrentRow(0)
        
    def load_selected_announcement(self, item):
        """加载选中的公告"""
        announcement = item.data(Qt.UserRole)
        if announcement:
            self.announcement_display.setHtml(announcement.get("content", ""))
            
    def close_announcement_panel(self):
        """关闭公告面板"""
        self.announcement_dock.close()
        
    # 添加安装包接收区域
    def create_update_panel(self):
        """创建安装包接收区域"""
        self.update_dock = QDockWidget("更新管理", self)
        self.update_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.update_dock.hide()  # 默认隐藏
        
        # 创建更新管理区域
        update_widget = QWidget()
        update_layout = QVBoxLayout(update_widget)
        
        # 更新信息显示
        self.update_info = QTextBrowser()
        self.update_info.setStyleSheet("""
            QTextBrowser {
                background-color: #fff8dc;
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 10px;
                font-family: Microsoft YaHei, sans-serif;
            }
        """)
        self.update_info.setHtml("<p>暂无可用更新</p>")
        
        # 更新操作按钮
        update_btn_layout = QHBoxLayout()
        self.check_update_btn = QPushButton("检查更新")
        self.download_update_btn = QPushButton("下载更新")
        self.install_update_btn = QPushButton("安装更新")
        self.download_update_btn.setEnabled(False)
        self.install_update_btn.setEnabled(False)
        
        self.check_update_btn.clicked.connect(self.check_for_updates)
        self.download_update_btn.clicked.connect(self.download_update)
        self.install_update_btn.clicked.connect(self.install_update)
        
        update_btn_layout.addWidget(self.check_update_btn)
        update_btn_layout.addWidget(self.download_update_btn)
        update_btn_layout.addWidget(self.install_update_btn)
        update_btn_layout.addStretch()
        
        update_layout.addWidget(QLabel("更新信息："))
        update_layout.addWidget(self.update_info)
        update_layout.addLayout(update_btn_layout)
        
        self.update_dock.setWidget(update_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.update_dock)
        
    def check_for_updates(self):
        """检查更新"""
        self.update_info.setHtml("<p>正在检查更新...</p>")
        # 在实际应用中，这里会连接到更新服务器检查更新
        # 目前我们模拟检查结果
        QTimer.singleShot(1000, self.simulate_update_check)
        
    def simulate_update_check(self):
        """模拟更新检查结果"""
        # 模拟有新版本的情况
        new_version_available = True
        
        if new_version_available:
            update_info = """
            <h3>发现新版本</h3>
            <p><b>版本：</b>v2.1</p>
            <p><b>更新内容：</b></p>
            <ul>
                <li>新增P2P局域网通信功能</li>
                <li>优化AI处理性能</li>
                <li>修复已知问题</li>
                <li>提升系统稳定性</li>
            </ul>
            <p>建议立即下载更新以获得最新功能。</p>
            """
            self.update_info.setHtml(update_info)
            self.download_update_btn.setEnabled(True)
        else:
            self.update_info.setHtml("<p>当前已是最新版本</p>")
            self.download_update_btn.setEnabled(False)
            
    def download_update(self):
        """下载更新"""
        self.update_info.setHtml("<p>正在下载更新...</p>")
        self.download_update_btn.setEnabled(False)
        # 模拟下载过程
        QTimer.singleShot(2000, self.simulate_download_complete)
        
    def simulate_download_complete(self):
        """模拟下载完成"""
        self.update_info.setHtml("<p>更新下载完成，准备安装。</p>")
        self.install_update_btn.setEnabled(True)
        
    def install_update(self):
        """安装更新"""
        reply = QMessageBox.question(
            self, "确认安装", 
            "确定要安装更新吗？浏览器将重启以完成更新。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            QMessageBox.information(self, "更新", "更新安装完成，请重新启动浏览器。")
            self.update_info.setHtml("<p>更新已安装，请重启浏览器。</p>")
            self.install_update_btn.setEnabled(False)

    def keyPressEvent(self, event):
        """处理按键事件"""
        # F12 快捷键打开/关闭开发者工具
        if event.key() == Qt.Key_F12:
            self.toggle_dev_tools()
        else:
            super().keyPressEvent(event)