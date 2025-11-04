#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
道衍AI浏览器 - 局域网更新服务器启动脚本
"""

import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QTextEdit, QLabel, QFileDialog, QMessageBox,
    QGroupBox, QListWidget, QListWidgetItem, QSplitter, QMenu
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCursor
import json
from datetime import datetime
import uuid
import threading
import time

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from server import UpdateServer
    SERVER_AVAILABLE = True
except ImportError as e:
    SERVER_AVAILABLE = False
    print(f"服务器模块导入错误: {e}")

class ServerThread(QThread):
    """服务器线程"""
    server_started = pyqtSignal(str)
    server_error = pyqtSignal(str)
    
    def __init__(self, host='0.0.0.0', port=8080):
        super().__init__()
        self.host = host
        self.port = port
        self.server = None
        self.running = True
        
    def run(self):
        try:
            if SERVER_AVAILABLE:
                self.server = UpdateServer(host=self.host, port=self.port)
                self.server_started.emit(f"服务器启动成功: http://{self.host}:{self.port}")
                self.server.start_server()
                # 保持服务器运行
                while self.running:
                    self.msleep(100)
            else:
                self.server_error.emit("服务器模块不可用")
        except Exception as e:
            self.server_error.emit(f"服务器启动失败: {str(e)}")
            
    def stop(self):
        self.running = False
        if self.server:
            self.server.stop_server()

class UpdateServerGUI(QMainWindow):
    """更新服务器图形界面"""
    
    def __init__(self):
        super().__init__()
        self.server_thread = None
        self.messages = []  # 存储消息历史
        self.load_message_history()  # 加载历史消息
        self.init_ui()
        self.start_server()  # 启动时自动开启服务器
        
    def init_ui(self):
        self.setWindowTitle("道衍AI浏览器 - 局域网更新服务器")
        self.setGeometry(100, 100, 900, 700)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 服务器状态区域
        status_group = QGroupBox("服务器状态")
        status_layout = QHBoxLayout()
        self.status_label = QLabel("服务器未启动")
        self.start_btn = QPushButton("启动服务器")
        self.stop_btn = QPushButton("停止服务器")
        self.stop_btn.setEnabled(False)
        
        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn.clicked.connect(self.stop_server)
        
        status_layout.addWidget(QLabel("状态:"))
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.start_btn)
        status_layout.addWidget(self.stop_btn)
        status_group.setLayout(status_layout)
        
        # 创建分割器用于左右布局
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：公告管理
        announcement_widget = QWidget()
        announcement_layout = QVBoxLayout(announcement_widget)
        
        announcement_group = QGroupBox("公告管理")
        announcement_group_layout = QVBoxLayout()
        
        self.announcement_title = QTextEdit()
        self.announcement_title.setMaximumHeight(30)
        self.announcement_title.setPlaceholderText("公告标题")
        
        self.announcement_content = QTextEdit()
        self.announcement_content.setPlaceholderText("公告内容")
        
        announcement_btn_layout = QHBoxLayout()
        self.send_announcement_btn = QPushButton("发送公告")
        self.send_announcement_btn.clicked.connect(self.send_announcement)
        announcement_btn_layout.addStretch()
        announcement_btn_layout.addWidget(self.send_announcement_btn)
        
        announcement_group_layout.addWidget(QLabel("公告标题:"))
        announcement_group_layout.addWidget(self.announcement_title)
        announcement_group_layout.addWidget(QLabel("公告内容:"))
        announcement_group_layout.addWidget(self.announcement_content)
        announcement_group_layout.addLayout(announcement_btn_layout)
        announcement_group.setLayout(announcement_group_layout)
        
        # 历史公告列表
        history_group = QGroupBox("历史公告")
        history_layout = QVBoxLayout()
        self.announcement_list = QListWidget()
        self.announcement_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.announcement_list.customContextMenuRequested.connect(self.show_announcement_context_menu)
        self.announcement_list.itemClicked.connect(self.load_selected_announcement)
        history_layout.addWidget(self.announcement_list)
        history_group.setLayout(history_layout)
        
        announcement_layout.addWidget(announcement_group)
        announcement_layout.addWidget(history_group)
        
        # 右侧：更新包管理
        update_widget = QWidget()
        update_layout = QVBoxLayout(update_widget)
        
        update_group = QGroupBox("更新包管理")
        update_group_layout = QVBoxLayout()
        
        self.update_info = QTextEdit()
        self.update_info.setMaximumHeight(100)
        self.update_info.setPlaceholderText("更新包信息")
        self.update_info.setReadOnly(True)
        
        update_btn_layout = QHBoxLayout()
        self.select_update_btn = QPushButton("选择更新包")
        self.send_update_btn = QPushButton("发送更新")
        self.select_update_btn.clicked.connect(self.select_update_package)
        self.send_update_btn.clicked.connect(self.send_update_package)
        self.send_update_btn.setEnabled(False)
        update_btn_layout.addWidget(self.select_update_btn)
        update_btn_layout.addWidget(self.send_update_btn)
        
        update_group_layout.addWidget(QLabel("更新包信息:"))
        update_group_layout.addWidget(self.update_info)
        update_group_layout.addLayout(update_btn_layout)
        update_group.setLayout(update_group_layout)
        
        # 更新包历史列表
        update_history_group = QGroupBox("更新包历史")
        update_history_layout = QVBoxLayout()
        self.update_list = QListWidget()
        update_history_layout.addWidget(self.update_list)
        update_history_group.setLayout(update_history_layout)
        
        update_layout.addWidget(update_group)
        update_layout.addWidget(update_history_group)
        
        # 添加到分割器
        splitter.addWidget(announcement_widget)
        splitter.addWidget(update_widget)
        splitter.setSizes([400, 400])
        
        # 添加到主布局
        main_layout.addWidget(status_group)
        main_layout.addWidget(splitter)
        
        # 加载历史数据
        self.load_history_announcements()
        
        # 添加菜单栏提示
        self.statusBar().showMessage("准备就绪")
        
    def start_server(self):
        """启动服务器"""
        try:
            self.server_thread = ServerThread(host='0.0.0.0', port=8080)
            self.server_thread.server_started.connect(self.on_server_started)
            self.server_thread.server_error.connect(self.on_server_error)
            self.server_thread.start()
            
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_label.setText("正在启动服务器...")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动服务器时出错: {str(e)}")
            
    def stop_server(self):
        """停止服务器"""
        if self.server_thread:
            self.server_thread.stop()
            self.server_thread.quit()
            self.server_thread.wait()
            self.server_thread = None
            
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("已停止")
        self.statusBar().showMessage("服务器已停止")
            
    def on_server_started(self, message):
        """服务器启动成功"""
        self.status_label.setText("运行中")
        self.statusBar().showMessage(message)
        
    def on_server_error(self, error_message):
        """服务器启动失败"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("启动失败")
        QMessageBox.critical(self, "服务器错误", error_message)
        self.statusBar().showMessage(error_message)
        
    def send_announcement(self):
        """发送公告"""
        title = self.announcement_title.toPlainText().strip()
        content = self.announcement_content.toPlainText().strip()
        
        if not title or not content:
            QMessageBox.warning(self, "警告", "请填写公告标题和内容")
            return
            
        try:
            # 创建公告数据，添加唯一ID和时间戳
            announcement = {
                "id": str(uuid.uuid4()),  # 唯一ID
                "type": "announcement",
                "title": title,
                "content": content,
                "version": "1.0",  # 默认版本
                "timestamp": datetime.now().isoformat()  # 时间戳
            }
            
            # 保存公告到历史记录
            self.messages.append(announcement)
            self.save_message_history()
            
            # 添加到历史列表
            item_text = f"[{datetime.now().strftime('%H:%M:%S')}] {title}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, announcement)
            self.announcement_list.insertItem(0, item)
            
            # 通知服务器更新公告
            if SERVER_AVAILABLE:
                server = UpdateServer()
                server.save_announcement({
                    "title": title,
                    "content": content,
                    "version": "1.0"
                })
                
            QMessageBox.information(self, "成功", "公告已发送")
            self.statusBar().showMessage("公告发送成功")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发送公告失败: {str(e)}")
            
    def delete_announcement(self, item):
        """删除公告"""
        try:
            announcement = item.data(Qt.UserRole)
            if announcement:
                message_id = announcement.get('id')
                if message_id:
                    # 从历史记录中移除
                    self.messages = [msg for msg in self.messages if msg.get('id') != message_id]
                    self.save_message_history()
                    
                    # 从列表中移除
                    self.announcement_list.takeItem(self.announcement_list.row(item))
                    
                    # 发送删除通知给客户端
                    delete_message = {
                        "id": str(uuid.uuid4()),
                        "type": "delete",
                        "deleted_id": message_id,
                        "timestamp": datetime.now().isoformat()
                    }
                    self.messages.append(delete_message)
                    self.save_message_history()
                    
                    QMessageBox.information(self, "成功", "公告已删除并通知客户端")
                    self.statusBar().showMessage("公告已删除")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除公告失败: {str(e)}")
            
    def show_announcement_context_menu(self, position):
        """显示公告右键菜单"""
        item = self.announcement_list.itemAt(position)
        if item:
            menu = QMenu()
            delete_action = menu.addAction("删除公告")
            action = menu.exec_(QCursor.pos())
            if action == delete_action:
                self.delete_announcement(item)
            
    def select_update_package(self):
        """选择更新包"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择更新包", "", "所有文件 (*.*)"
        )
        
        if file_path:
            try:
                file_size = os.path.getsize(file_path)
                file_name = os.path.basename(file_path)
                
                info_text = f"文件名: {file_name}\n大小: {file_size} 字节\n路径: {file_path}"
                self.update_info.setText(info_text)
                self.selected_update_path = file_path
                self.send_update_btn.setEnabled(True)
                self.statusBar().showMessage(f"已选择更新包: {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"读取文件信息失败: {str(e)}")
                
    def send_update_package(self):
        """发送更新包"""
        if not hasattr(self, 'selected_update_path'):
            QMessageBox.warning(self, "警告", "请先选择更新包")
            return
            
        try:
            # 这里应该实现更新包的处理逻辑
            # 在实际应用中，会将文件复制到服务器目录并生成版本信息
            file_name = os.path.basename(self.selected_update_path)
            item_text = f"[{datetime.now().strftime('%H:%M:%S')}] {file_name}"
            self.update_list.insertItem(0, QListWidgetItem(item_text))
            
            QMessageBox.information(self, "成功", "更新包已添加到服务器")
            self.statusBar().showMessage("更新包发送成功")
            
            # 清空选择
            self.update_info.clear()
            self.send_update_btn.setEnabled(False)
            delattr(self, 'selected_update_path')
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发送更新包失败: {str(e)}")
            
    def load_selected_announcement(self, item):
        """加载选中的公告"""
        announcement = item.data(Qt.UserRole)
        if announcement:
            self.announcement_title.setText(announcement.get("title", ""))
            self.announcement_content.setText(announcement.get("content", ""))
            
    def load_history_announcements(self):
        """加载历史公告到界面"""
        for message in self.messages:
            if message.get("type") == "announcement":
                timestamp = message.get("timestamp", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        time_str = dt.strftime('%H:%M:%S')
                    except:
                        time_str = "未知时间"
                else:
                    time_str = "未知时间"
                    
                title = message.get("title", "无标题")
                item_text = f"[{time_str}] {title}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, message)
                self.announcement_list.insertItem(0, item)
            
    def load_message_history(self):
        """加载消息历史"""
        try:
            if os.path.exists('server_message_history.json'):
                with open('server_message_history.json', 'r', encoding='utf-8') as f:
                    self.messages = json.load(f)
            else:
                self.messages = []
        except Exception as e:
            print(f"加载消息历史失败: {e}")
            self.messages = []
            
    def save_message_history(self):
        """保存消息历史"""
        try:
            with open('server_message_history.json', 'w', encoding='utf-8') as f:
                json.dump(self.messages, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存消息历史失败: {e}")
        
    def closeEvent(self, event):
        """关闭事件 - 仅关闭GUI，不关闭服务器"""
        # 断开服务器线程与GUI的连接，但不停止服务器
        if self.server_thread:
            # 断开信号连接
            self.server_thread.server_started.disconnect()
            self.server_thread.server_error.disconnect()
            # 将线程设置为分离状态，这样即使GUI关闭，服务器仍可继续运行
            self.server_thread.setParent(None)
            
        event.accept()

def show_install_instructions():
    """显示cryptography库安装说明"""
    instructions = """
cryptography库安装说明:

1. 在命令提示符或终端中运行以下命令:
   pip install cryptography

2. 如果pip安装失败，可以尝试:
   pip install --upgrade pip
   pip install cryptography

3. 在某些系统上可能需要安装额外的依赖:
   - Windows: 通常不需要额外依赖
   - Linux: 可能需要安装 libffi-dev, libssl-dev 等
   - macOS: 可能需要安装 Xcode Command Line Tools

4. 如果仍然无法安装，可以尝试使用conda:
   conda install cryptography

5. 安装完成后重启应用程序
    """
    
    msg_box = QMessageBox()
    msg_box.setWindowTitle("cryptography库安装说明")
    msg_box.setText(instructions)
    msg_box.setStandardButtons(QMessageBox.Ok)
    msg_box.exec_()

def main():
    app = QApplication(sys.argv)
    
    # 检查cryptography库
    try:
        from cryptography.fernet import Fernet
        has_crypto = True
    except ImportError:
        has_crypto = False
    
    if not has_crypto:
        reply = QMessageBox.question(
            None, "缺少依赖", 
            "检测到未安装cryptography库，这将影响公告和更新的安全传输。\n是否查看安装说明？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            show_install_instructions()
    
    # 创建并显示主窗口
    window = UpdateServerGUI()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()