import json
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, 
    QTreeWidgetItem, QHeaderView, QFileDialog, QMessageBox
)
from PyQt5.QtCore import QUrl

class BookmarksManager(QDialog):
    """书签管理器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("书签管理器")
        self.setGeometry(300, 300, 800, 500)
        self.bookmarks_file = "bookmarks.json"
        self.setup_ui()
        self.load_bookmarks()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("添加书签")
        self.delete_btn = QPushButton("删除书签")
        self.import_btn = QPushButton("导入")
        self.export_btn = QPushButton("导出")

        self.add_btn.clicked.connect(self.add_bookmark)
        self.delete_btn.clicked.connect(self.delete_bookmark)
        self.import_btn.clicked.connect(self.import_bookmarks)
        self.export_btn.clicked.connect(self.export_bookmarks)

        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.export_btn)
        toolbar.addStretch()

        # 书签列表
        self.bookmarks_list = QTreeWidget()
        self.bookmarks_list.setHeaderLabels(["标题", "网址", "添加时间"])
        self.bookmarks_list.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.bookmarks_list.itemDoubleClicked.connect(self.open_bookmark)

        layout.addLayout(toolbar)
        layout.addWidget(self.bookmarks_list)

    def add_bookmark(self, title="", url=""):
        """添加书签"""
        if not title or not url:
            # 从父窗口获取当前页面信息
            if self.parent():
                browser = self.parent().tab_widget.currentWidget()
                if isinstance(browser, QWebEngineView):
                    title = browser.title()
                    url = browser.url().toString()
        
        if title and url:
            self.bookmarks.append({
                "title": title,
                "url": url,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            self.refresh_list()
            self.save_bookmarks()

    def delete_bookmark(self):
        """删除书签"""
        current_item = self.bookmarks_list.currentItem()
        if current_item:
            index = self.bookmarks_list.indexOfTopLevelItem(current_item)
            if index >= 0:
                self.bookmarks.pop(index)
                self.refresh_list()
                self.save_bookmarks()

    def open_bookmark(self, item, column):
        """打开书签"""
        url = item.text(1)
        if self.parent():
            from PyQt5.QtWebEngineWidgets import QWebEngineView
            self.parent().add_new_tab(QUrl(url))

    def import_bookmarks(self):
        """导入书签"""
        path, _ = QFileDialog.getOpenFileName(self, "导入书签", "", "JSON文件 (*.json)")
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    imported_bookmarks = json.load(f)
                self.bookmarks.extend(imported_bookmarks)
                self.refresh_list()
                self.save_bookmarks()
                QMessageBox.information(self, "成功", "书签导入成功")
            except Exception as e:
                QMessageBox.critical(self, "失败", f"导入失败: {e}")

    def export_bookmarks(self):
        """导出书签"""
        path, _ = QFileDialog.getSaveFileName(self, "导出书签", "", "JSON文件 (*.json)")
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.bookmarks, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "成功", "书签导出成功")
            except Exception as e:
                QMessageBox.critical(self, "失败", f"导出失败: {e}")

    def refresh_list(self):
        """刷新列表"""
        self.bookmarks_list.clear()
        for bookmark in self.bookmarks:
            item = QTreeWidgetItem(self.bookmarks_list)
            item.setText(0, bookmark["title"])
            item.setText(1, bookmark["url"])
            item.setText(2, bookmark["time"])
            self.bookmarks_list.addTopLevelItem(item)

    def save_bookmarks(self):
        """保存书签到文件"""
        try:
            with open(self.bookmarks_file, 'w', encoding='utf-8') as f:
                json.dump(self.bookmarks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存书签失败: {e}")

    def load_bookmarks(self):
        """从文件加载书签"""
        self.bookmarks = []
        if os.path.exists(self.bookmarks_file):
            try:
                with open(self.bookmarks_file, 'r', encoding='utf-8') as f:
                    self.bookmarks = json.load(f)
                self.refresh_list()
            except Exception as e:
                print(f"加载书签失败: {e}")
                self.bookmarks = []