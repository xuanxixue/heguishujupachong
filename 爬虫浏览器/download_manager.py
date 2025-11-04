import os
import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, 
    QTreeWidgetItem, QHeaderView
)
from PyQt5.QtWebEngineWidgets import QWebEngineDownloadItem
from PyQt5.QtCore import QStandardPaths

class DownloadManager(QDialog):
    """下载管理器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("下载管理器")
        self.setGeometry(300, 300, 800, 500)
        self.setup_ui()
        self.downloads = []

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QHBoxLayout()
        self.clear_btn = QPushButton("清空已完成")
        self.open_folder_btn = QPushButton("打开下载文件夹")
        self.pause_all_btn = QPushButton("暂停全部")
        self.resume_all_btn = QPushButton("继续全部")

        self.clear_btn.clicked.connect(self.clear_completed)
        self.open_folder_btn.clicked.connect(self.open_download_folder)
        self.pause_all_btn.clicked.connect(self.pause_all)
        self.resume_all_btn.clicked.connect(self.resume_all)

        toolbar.addWidget(self.clear_btn)
        toolbar.addWidget(self.open_folder_btn)
        toolbar.addWidget(self.pause_all_btn)
        toolbar.addWidget(self.resume_all_btn)
        toolbar.addStretch()

        # 下载列表
        self.download_list = QTreeWidget()
        self.download_list.setHeaderLabels(["文件名", "进度", "状态", "大小", "速度", "剩余时间"])
        self.download_list.header().setSectionResizeMode(0, QHeaderView.Stretch)

        layout.addLayout(toolbar)
        layout.addWidget(self.download_list)

    def add_download(self, download_item):
        """添加新的下载项"""
        item = QTreeWidgetItem(self.download_list)
        item.download = download_item
        self.downloads.append(item)
        
        filename = os.path.basename(download_item.path())
        item.setText(0, filename)
        item.setText(1, "0%")
        item.setText(2, "下载中")
        item.setText(3, "未知")
        item.setText(4, "0 KB/s")
        item.setText(5, "未知")
        
        # 连接信号
        download_item.downloadProgress.connect(lambda bytes_received, bytes_total: 
                                             self.update_progress(item, bytes_received, bytes_total))
        download_item.finished.connect(lambda: self.download_finished(item))
        
        self.download_list.addTopLevelItem(item)

    def update_progress(self, item, bytes_received, bytes_total):
        """更新下载进度"""
        if bytes_total > 0:
            percent = int((bytes_received / bytes_total) * 100)
            item.setText(1, f"{percent}%")
            
            # 计算下载速度（简化版）
            speed = "计算中..."
            time_left = "计算中..."
            
            item.setText(2, "下载中")
            item.setText(3, f"{bytes_received//1024}KB / {bytes_total//1024}KB")
            item.setText(4, speed)
            item.setText(5, time_left)

    def download_finished(self, item):
        """下载完成"""
        if item.download.state() == QWebEngineDownloadItem.DownloadCompleted:
            item.setText(1, "100%")
            item.setText(2, "已完成")
            item.setText(4, "")
            item.setText(5, "")
        else:
            item.setText(2, "失败")

    def clear_completed(self):
        """清除已完成的下载"""
        for i in range(self.download_list.topLevelItemCount() - 1, -1, -1):
            item = self.download_list.topLevelItem(i)
            if item.text(2) in ["已完成", "失败"]:
                self.download_list.takeTopLevelItem(i)

    def open_download_folder(self):
        """打开下载文件夹"""
        download_path = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        if os.path.exists(download_path):
            if os.name == 'nt':  # Windows
                os.startfile(download_path)
            elif os.name == 'posix':  # Linux or macOS
                if sys.platform == 'darwin':  # macOS
                    os.system(f'open "{download_path}"')
                else:  # Linux
                    os.system(f'xdg-open "{download_path}"')

    def pause_all(self):
        """暂停所有下载"""
        for item in self.downloads:
            if hasattr(item, 'download') and item.download.state() == QWebEngineDownloadItem.DownloadInProgress:
                item.download.pause()
                item.setText(2, "已暂停")

    def resume_all(self):
        """继续所有下载"""
        for item in self.downloads:
            if hasattr(item, 'download') and item.download.state() == QWebEngineDownloadItem.DownloadPaused:
                item.download.resume()
                item.setText(2, "下载中")