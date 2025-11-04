import os
import json
import hashlib
import requests
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTextEdit, QProgressBar, QMessageBox, QLineEdit, QFormLayout,
    QGroupBox, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
# 修改导入方式，使其在模块不可用时不会导致程序崩溃
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
import socket
import threading
from datetime import datetime
import urllib.parse

class P2PWorker(QThread):
    """P2P通信工作线程"""
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    p2p_finished = pyqtSignal(bool, str)
    announcement_received = pyqtSignal(dict)
    version_info_received = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.local_ip = self.get_local_ip()
        self.announcement = {
            "title": "局域网公告",
            "content": "欢迎使用道衍AI浏览器局域网功能",
            "publish_time": datetime.now().isoformat(),
            "version": "2.0"
        }
        self.version_info = {
            "version": "2.0",
            "description": "当前版本",
            "publish_time": datetime.now().isoformat(),
            "filename": "browser_v2.0.exe"
        }
        self.running = True
        self.udp_port = 12345
        self.tcp_port = 12346
        
    def get_local_ip(self):
        """获取本地IP地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
            
    def run(self):
        """运行P2P通信"""
        try:
            self.status_updated.emit("启动局域网服务...")
            self.progress_updated.emit(10)
            
            # 启动UDP广播监听线程
            udp_thread = threading.Thread(target=self.listen_udp_broadcast, daemon=True)
            udp_thread.start()
            
            # 启动TCP服务线程
            tcp_thread = threading.Thread(target=self.listen_tcp_requests, daemon=True)
            tcp_thread.start()
            
            self.progress_updated.emit(100)
            self.status_updated.emit("局域网服务已启动")
            
            # 保持线程运行
            while self.running:
                self.msleep(100)
                
        except Exception as e:
            self.p2p_finished.emit(False, f"启动失败: {str(e)}")
            
    def listen_udp_broadcast(self):
        """监听UDP广播消息"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("", self.udp_port))
        
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                message = json.loads(data.decode('utf-8'))
                
                if message.get("type") == "discovery":
                    # 回复自己的信息
                    response = {
                        "type": "response",
                        "ip": self.local_ip,
                        "announcement": self.announcement,
                        "version_info": self.version_info
                    }
                    sock.sendto(json.dumps(response).encode('utf-8'), addr)
                    
                elif message.get("type") == "announcement_request":
                    # 发送公告
                    self.announcement_received.emit(self.announcement)
                    
                elif message.get("type") == "version_request":
                    # 发送版本信息
                    self.version_info_received.emit(self.version_info)
                    
            except Exception:
                pass
                
    def listen_tcp_requests(self):
        """监听TCP请求"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("", self.tcp_port))
        server_socket.listen(5)
        
        while self.running:
            try:
                client_socket, addr = server_socket.accept()
                # 在实际应用中，这里可以处理文件传输等请求
                client_socket.close()
            except Exception:
                pass
                
    def broadcast_discovery(self):
        """广播发现消息"""
        self.status_updated.emit("搜索局域网中的设备...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        message = {"type": "discovery"}
        sock.sendto(json.dumps(message).encode('utf-8'), ('<broadcast>', self.udp_port))
        sock.close()
        
    def request_announcement(self):
        """请求公告"""
        self.status_updated.emit("获取公告信息...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        message = {"type": "announcement_request"}
        sock.sendto(json.dumps(message).encode('utf-8'), ('<broadcast>', self.udp_port))
        sock.close()
        
    def request_version_info(self):
        """请求版本信息"""
        self.status_updated.emit("检查最新版本...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        message = {"type": "version_request"}
        sock.sendto(json.dumps(message).encode('utf-8'), ('<broadcast>', self.udp_port))
        sock.close()
        
    def stop(self):
        """停止P2P服务"""
        self.running = False

class HTTPUpdateWorker(QThread):
    """HTTP更新工作线程"""
    update_progress = pyqtSignal(int)
    update_status = pyqtSignal(str)
    update_finished = pyqtSignal(bool, str, object)
    
    def __init__(self, server_url, parent=None):
        super().__init__(parent)
        self.server_url = server_url.rstrip('/')
        
    def run(self):
        try:
            self.update_status.emit("连接到更新服务器...")
            self.update_progress.emit(10)
            
            # 获取公告
            self.update_status.emit("获取公告信息...")
            announcement_url = f"{self.server_url}/announcement"
            response = requests.get(announcement_url, timeout=10)
            if response.status_code == 200:
                announcement = response.json()
                self.update_progress.emit(30)
            else:
                announcement = None
                
            # 获取最新版本信息
            self.update_status.emit("检查最新版本...")
            version_url = f"{self.server_url}/version/latest"
            response = requests.get(version_url, timeout=10)
            if response.status_code == 200:
                version_info = response.json()
                self.update_progress.emit(60)
            else:
                version_info = None
                
            self.update_progress.emit(100)
            self.update_status.emit("检查完成")
            self.update_finished.emit(True, "检查完成", {
                "announcement": announcement,
                "version_info": version_info
            })
        except Exception as e:
            self.update_finished.emit(False, f"检查更新失败: {str(e)}", None)

class UpdateManager(QDialog):
    """更新管理器（支持P2P和HTTP模式）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("局域网通信")
        self.setGeometry(300, 300, 600, 600)
        self.current_version = "2.0"
        self.latest_version_info = None
        self.p2p_worker = None
        self.http_worker = None
        # 固定服务器地址，禁止更改
        self.server_url = "http://localhost:8080"  # 默认服务器地址
        self.setup_ui()
        self.start_p2p_service()
        
        # 添加定时器用于轮询服务器
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_server)
        self.poll_timer.start(5000)  # 每5秒轮询一次
        
        # 存储已接收的消息ID
        self.received_message_ids = set()
        self.load_message_history()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 服务器设置（只读显示，禁止更改）
        server_group = QGroupBox("服务器设置")
        server_layout = QHBoxLayout()
        self.server_url_edit = QLineEdit(self.server_url)
        self.server_url_edit.setReadOnly(True)  # 禁止编辑
        server_layout.addWidget(QLabel("服务器地址:"))
        server_layout.addWidget(self.server_url_edit)
        server_group.setLayout(server_layout)
        
        # 网络信息
        network_group = QGroupBox("网络信息")
        network_layout = QVBoxLayout()
        self.local_ip_label = QLabel("本地IP: 获取中...")
        network_layout.addWidget(self.local_ip_label)
        network_group.setLayout(network_layout)
        
        # 公告区域
        announcement_group = QGroupBox("公告信息")
        announcement_layout = QVBoxLayout()
        self.announcement_text = QTextEdit()
        self.announcement_text.setReadOnly(True)
        self.announcement_text.setMaximumHeight(150)
        announcement_layout.addWidget(self.announcement_text)
        announcement_group.setLayout(announcement_layout)
        
        # 版本信息
        version_group = QGroupBox("版本信息")
        version_layout = QVBoxLayout()
        self.version_info_text = QTextEdit()
        self.version_info_text.setReadOnly(True)
        self.version_info_text.setMaximumHeight(100)
        version_layout.addWidget(self.version_info_text)
        version_group.setLayout(version_layout)
        
        # 更新包列表
        packages_group = QGroupBox("可用更新")
        packages_layout = QVBoxLayout()
        self.packages_list = QListWidget()
        packages_layout.addWidget(self.packages_list)
        packages_group.setLayout(packages_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        
        # 按钮
        button_layout = QHBoxLayout()
        self.discovery_btn = QPushButton("发现设备")
        self.announcement_btn = QPushButton("获取公告")
        self.version_btn = QPushButton("检查版本")
        self.download_btn = QPushButton("下载更新")
        self.download_btn.setEnabled(False)
        self.close_btn = QPushButton("关闭")
        
        self.discovery_btn.clicked.connect(self.broadcast_discovery)
        self.announcement_btn.clicked.connect(self.request_announcement)
        self.version_btn.clicked.connect(self.request_version_info)
        self.download_btn.clicked.connect(self.download_update)
        self.close_btn.clicked.connect(self.close)
        
        button_layout.addWidget(self.discovery_btn)
        button_layout.addWidget(self.announcement_btn)
        button_layout.addWidget(self.version_btn)
        button_layout.addWidget(self.download_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        
        layout.addWidget(server_group)
        layout.addWidget(network_group)
        layout.addWidget(announcement_group)
        layout.addWidget(version_group)
        layout.addWidget(packages_group)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addLayout(button_layout)
        
    def start_p2p_service(self):
        """启动P2P服务"""
        self.p2p_worker = P2PWorker()
        self.p2p_worker.progress_updated.connect(self.progress_bar.setValue)
        self.p2p_worker.status_updated.connect(self.status_label.setText)
        self.p2p_worker.announcement_received.connect(self.on_announcement_received)
        self.p2p_worker.version_info_received.connect(self.on_version_info_received)
        self.p2p_worker.p2p_finished.connect(self.on_p2p_finished)
        self.p2p_worker.start()
        
        # 更新本地IP显示
        self.local_ip_label.setText(f"本地IP: {self.p2p_worker.local_ip}")
        
    def broadcast_discovery(self):
        """广播发现消息"""
        if self.p2p_worker:
            self.p2p_worker.broadcast_discovery()
            
    def request_announcement(self):
        """请求公告"""
        if self.p2p_worker:
            self.p2p_worker.request_announcement()
            
    def request_version_info(self):
        """请求版本信息"""
        if self.p2p_worker:
            self.p2p_worker.request_version_info()
            
    def download_update(self):
        """下载更新"""
        if not self.latest_version_info:
            QMessageBox.warning(self, "警告", "没有可用的更新")
            return
            
        reply = QMessageBox.question(
            self, "确认下载", 
            f"确定要下载版本 {self.latest_version_info.get('version')} 的更新吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 构造下载URL
                version = self.latest_version_info.get('version')
                download_url = f"{self.server_url}/download/{version}"
                
                # 这里应该实现实际的下载逻辑
                # 为简化，我们只显示下载信息
                QMessageBox.information(
                    self, "下载", 
                    f"开始下载更新...\n\n"
                    f"版本: {self.latest_version_info.get('version')}\n"
                    f"文件: {self.latest_version_info.get('filename')}\n"
                    f"描述: {self.latest_version_info.get('description')}\n\n"
                    f"实际应用中将从以下地址下载:\n{download_url}"
                )
            except Exception as e:
                QMessageBox.critical(self, "下载失败", f"下载更新时出错: {str(e)}")
    
    def poll_server(self):
        """轮询服务器获取新消息"""
        try:
            # 获取服务器上的消息列表
            response = requests.get(f"{self.server_url}/messages", timeout=5)
            if response.status_code == 200:
                messages = response.json()
                for message in messages:
                    message_id = message.get('id')
                    if message_id and message_id not in self.received_message_ids:
                        # 新消息，处理它
                        self.process_new_message(message)
                        self.received_message_ids.add(message_id)
                # 保存消息历史
                self.save_message_history()
        except Exception as e:
            pass  # 静默处理网络错误
            
    def process_new_message(self, message):
        """处理新收到的消息"""
        message_type = message.get('type', 'announcement')
        if message_type == 'announcement':
            self.on_announcement_received(message)
        elif message_type == 'delete':
            # 处理删除消息
            deleted_id = message.get('deleted_id')
            if deleted_id:
                self.remove_message_by_id(deleted_id)
                
    def remove_message_by_id(self, message_id):
        """根据ID删除消息"""
        # 从已接收集合中移除
        self.received_message_ids.discard(message_id)
        # 重新加载消息历史
        self.load_message_history()
        # 更新UI显示
        self.refresh_message_display()
        
    def refresh_message_display(self):
        """刷新消息显示"""
        # 这里可以重新从服务器获取消息并更新显示
        pass
        
    def load_message_history(self):
        """加载消息历史"""
        try:
            if os.path.exists('message_history.json'):
                with open('message_history.json', 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    self.received_message_ids = set(history.get('received_ids', []))
        except Exception:
            self.received_message_ids = set()
            
    def save_message_history(self):
        """保存消息历史"""
        try:
            history = {
                'received_ids': list(self.received_message_ids),
                'last_updated': datetime.now().isoformat()
            }
            with open('message_history.json', 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
            
    def on_announcement_received(self, announcement):
        """收到公告"""
        content = f"<h3>{announcement.get('title', '公告')}</h3>"
        content += f"<p><b>发布时间:</b> {announcement.get('publish_time', '未知')}</p>"
        content += f"<p><b>版本:</b> {announcement.get('version', '未知')}</p>"
        content += f"<p>{announcement.get('content', '').replace(chr(10), '<br>')}</p>"
        self.announcement_text.setHtml(content)
        
    def on_version_info_received(self, version_info):
        """收到版本信息"""
        self.latest_version_info = version_info
        content = f"<p><b>版本:</b> {version_info.get('version', '未知')}</p>"
        content += f"<p><b>描述:</b> {version_info.get('description', '无描述')}</p>"
        content += f"<p><b>发布时间:</b> {version_info.get('publish_time', '未知')}</p>"
        content += f"<p><b>文件名:</b> {version_info.get('filename', '未知')}</p>"
        self.version_info_text.setHtml(content)
        
        # 检查是否有新版本
        if version_info.get('version') != self.current_version:
            self.status_label.setText(f"发现新版本: {version_info.get('version')}")
            self.download_btn.setEnabled(True)
        else:
            self.status_label.setText("当前已是最新版本")
            
        # 添加到更新包列表
        item_text = f"版本 {version_info.get('version')} - {version_info.get('filename')}"
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, version_info)
        self.packages_list.addItem(item)
            
    def on_p2p_finished(self, success, message):
        """P2P服务完成"""
        self.progress_bar.setVisible(False)
        if not success:
            self.status_label.setText(message)
            QMessageBox.warning(self, "服务错误", message)
            
    def on_http_update_finished(self, success, message, data):
        """HTTP更新检查完成"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(message)
        
        if success and data:
            # 显示公告
            announcement = data.get("announcement")
            if announcement:
                self.on_announcement_received(announcement)
                
            # 显示版本信息
            version_info = data.get("version_info")
            if version_info:
                self.on_version_info_received(version_info)
        elif not success:
            QMessageBox.warning(self, "更新检查失败", message)
            
    def closeEvent(self, event):
        """关闭事件"""
        if self.p2p_worker:
            self.p2p_worker.stop()
        # 停止轮询定时器
        self.poll_timer.stop()
        event.accept()