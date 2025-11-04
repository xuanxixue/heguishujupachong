import json
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, 
    QTreeWidgetItem, QHeaderView, QLabel, QLineEdit, QMessageBox
)
from PyQt5.QtCore import QUrl

class HistoryManager(QDialog):
    """历史记录管理器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("浏览历史")
        self.setGeometry(300, 300, 800, 500)
        self.history_file = "history.json"
        self.setup_ui()
        self.load_history()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索历史记录...")
        self.search_box.textChanged.connect(self.filter_history)
        
        self.clear_btn = QPushButton("清空历史")
        self.clear_btn.clicked.connect(self.clear_history)

        toolbar.addWidget(QLabel("搜索:"))
        toolbar.addWidget(self.search_box)
        toolbar.addStretch()
        toolbar.addWidget(self.clear_btn)

        # 历史列表
        self.history_list = QTreeWidget()
        self.history_list.setHeaderLabels(["标题", "网址", "访问时间"])
        self.history_list.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.history_list.itemDoubleClicked.connect(self.open_history_item)

        layout.addLayout(toolbar)
        layout.addWidget(self.history_list)

    def add_history(self, title, url):
        """添加历史记录"""
        self.history.append({
            "title": title,
            "url": url,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        self.refresh_list()
        self.save_history()

    def filter_history(self, text):
        """过滤历史记录"""
        for i in range(self.history_list.topLevelItemCount()):
            item = self.history_list.topLevelItem(i)
            match = (text.lower() in item.text(0).lower() or 
                    text.lower() in item.text(1).lower())
            item.setHidden(not match)

    def refresh_list(self):
        """刷新列表"""
        self.history_list.clear()
        for record in self.history:
            item = QTreeWidgetItem(self.history_list)
            item.setText(0, record["title"])
            item.setText(1, record["url"])
            item.setText(2, record["time"])
            self.history_list.addTopLevelItem(item)

    def open_history_item(self, item, column):
        """打开历史记录项"""
        url = item.text(1)
        if self.parent():
            self.parent().add_new_tab(QUrl(url))

    def clear_history(self):
        """清空历史记录"""
        if QMessageBox.question(self, "确认", "清空所有历史记录？") == QMessageBox.Yes:
            self.history.clear()
            self.history_list.clear()
            self.save_history()

    def save_history(self):
        """保存历史记录到文件"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存历史记录失败: {e}")

    def load_history(self):
        """从文件加载历史记录"""
        self.history = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
                self.refresh_list()
            except Exception as e:
                print(f"加载历史记录失败: {e}")
                self.history = []