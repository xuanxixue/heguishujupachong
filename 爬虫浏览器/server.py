import os
import json
import hashlib
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime
import threading
import uuid

# 尝试导入加密库
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("警告: cryptography库未安装，公告和更新将不加密传输")

class UpdateServer:
    """
    局域网更新服务器
    提供公告和软件更新服务
    """
    
    def __init__(self, host='localhost', port=8080, update_dir='updates'):
        self.host = host
        self.port = port
        self.update_dir = update_dir
        self.announcement_file = os.path.join(update_dir, 'announcement.json')
        self.versions_dir = os.path.join(update_dir, 'versions')
        self.key_file = os.path.join(update_dir, 'server.key')
        self.messages_file = os.path.join(update_dir, 'messages.json')  # 消息文件
        self.key = self._load_or_generate_key()
        self._setup_directories()
        self._init_announcement()
        self.messages = self._load_messages()  # 加载消息
        self.httpd = None
        self.server_thread = None
        
    def _load_or_generate_key(self):
        """加载或生成加密密钥"""
        if not CRYPTO_AVAILABLE:
            return None
            
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            return key
    
    def _setup_directories(self):
        """创建必要的目录"""
        os.makedirs(self.update_dir, exist_ok=True)
        os.makedirs(self.versions_dir, exist_ok=True)
    
    def _init_announcement(self):
        """初始化公告文件"""
        if not os.path.exists(self.announcement_file):
            default_announcement = {
                "title": "系统公告",
                "content": "欢迎使用道衍AI浏览器局域网更新服务",
                "publish_time": datetime.now().isoformat(),
                "version": "1.0"
            }
            self.save_announcement(default_announcement)
            
    def _load_messages(self):
        """加载消息历史"""
        if os.path.exists(self.messages_file):
            try:
                with open(self.messages_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_messages(self):
        """保存消息历史"""
        try:
            with open(self.messages_file, 'w', encoding='utf-8') as f:
                json.dump(self.messages, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存消息失败: {e}")
    
    def save_announcement(self, announcement):
        """保存公告"""
        announcement['publish_time'] = datetime.now().isoformat()
        with open(self.announcement_file, 'w', encoding='utf-8') as f:
            json.dump(announcement, f, ensure_ascii=False, indent=2)
        print(f"公告已更新: {announcement['title']}")
        
        # 添加到消息列表
        message = {
            "id": str(uuid.uuid4()),
            "type": "announcement",
            "title": announcement['title'],
            "content": announcement['content'],
            "version": announcement.get('version', '1.0'),
            "timestamp": announcement['publish_time']
        }
        self.messages.append(message)
        self._save_messages()
    
    def get_announcement(self):
        """获取公告"""
        if os.path.exists(self.announcement_file):
            with open(self.announcement_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def add_version(self, version, file_path, description=""):
        """添加新版本"""
        version_dir = os.path.join(self.versions_dir, version)
        os.makedirs(version_dir, exist_ok=True)
        
        # 复制更新文件
        filename = os.path.basename(file_path)
        dest_path = os.path.join(version_dir, filename)
        shutil.copy2(file_path, dest_path)
        
        # 计算文件哈希
        with open(dest_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        
        # 保存版本信息
        version_info = {
            "version": version,
            "filename": filename,
            "file_hash": file_hash,
            "description": description,
            "publish_time": datetime.now().isoformat()
        }
        
        info_file = os.path.join(version_dir, 'info.json')
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(version_info, f, ensure_ascii=False, indent=2)
        
        print(f"新版本已添加: {version}")
        return version_info
    
    def get_version_info(self, version):
        """获取版本信息"""
        info_file = os.path.join(self.versions_dir, version, 'info.json')
        if os.path.exists(info_file):
            with open(info_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def get_latest_version(self):
        """获取最新版本"""
        versions = []
        for version in os.listdir(self.versions_dir):
            if os.path.isdir(os.path.join(self.versions_dir, version)):
                version_info = self.get_version_info(version)
                if version_info:
                    versions.append(version_info)
        
        if versions:
            # 按版本号排序
            versions.sort(key=lambda x: x['version'], reverse=True)
            return versions[0]
        return None
    
    def get_messages(self):
        """获取所有消息"""
        return self.messages
    
    def start_server(self):
        """启动HTTP服务器"""
        self.httpd = HTTPServer((self.host, self.port), UpdateRequestHandler)
        self.httpd.update_server = self  # 将服务器实例附加到HTTP服务器
        
        # 在新线程中运行服务器
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        print(f"更新服务器启动在 http://{self.host}:{self.port}")
        print("按 Ctrl+C 停止服务器")
        
    def _run_server(self):
        """在独立线程中运行服务器"""
        try:
            self.httpd.serve_forever()
        except Exception as e:
            print(f"服务器运行出错: {e}")
            
    def stop_server(self):
        """停止HTTP服务器"""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.server_thread:
            self.server_thread.join(timeout=5)

class UpdateRequestHandler(BaseHTTPRequestHandler):
    """处理更新请求的HTTP处理器"""
    
    def do_GET(self):
        """处理GET请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == '/announcement':
            self._handle_announcement()
        elif path == '/version/latest':
            self._handle_latest_version()
        elif path == '/messages':
            self._handle_messages()
        elif path.startswith('/download/'):
            self._handle_download(path)
        else:
            self._send_error(404, "Not Found")
    
    def _handle_announcement(self):
        """处理公告请求"""
        announcement = self.server.update_server.get_announcement()
        if announcement:
            self._send_json(announcement)
        else:
            self._send_error(404, "Announcement not found")
    
    def _handle_latest_version(self):
        """处理最新版本请求"""
        version_info = self.server.update_server.get_latest_version()
        if version_info:
            self._send_json(version_info)
        else:
            self._send_error(404, "No versions available")
            
    def _handle_messages(self):
        """处理消息列表请求"""
        messages = self.server.update_server.get_messages()
        self._send_json(messages)
    
    def _handle_download(self, path):
        """处理下载请求"""
        # 解析版本号
        parts = path.split('/')
        if len(parts) < 3:
            self._send_error(400, "Bad Request")
            return
        
        version = parts[2]
        version_info = self.server.update_server.get_version_info(version)
        if not version_info:
            self._send_error(404, "Version not found")
            return
        
        file_path = os.path.join(
            self.server.update_server.versions_dir, 
            version, 
            version_info['filename']
        )
        
        if not os.path.exists(file_path):
            self._send_error(404, "File not found")
            return
        
        # 发送文件
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{version_info["filename"]}"')
            self.end_headers()
            
            with open(file_path, 'rb') as f:
                shutil.copyfileobj(f, self.wfile)
        except Exception as e:
            self._send_error(500, f"Error sending file: {str(e)}")
    
    def _send_json(self, data):
        """发送JSON响应"""
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')  # 允许跨域请求
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        except Exception as e:
            self._send_error(500, f"Error sending JSON: {str(e)}")
    
    def _send_error(self, code, message):
        """发送错误响应"""
        try:
            self.send_response(code)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(message.encode('utf-8'))
        except:
            pass  # 忽略发送错误时的异常
    
    def log_message(self, format, *args):
        """重写日志消息方法，减少输出"""
        pass  # 禁用默认的日志输出

def create_sample_update_package():
    """创建示例更新包"""
    # 创建一个简单的更新文件示例
    update_content = """
# 道衍AI浏览器更新包
这是一个示例更新包，实际使用时应包含完整的更新文件。
"""
    
    with open('sample_update.txt', 'w', encoding='utf-8') as f:
        f.write(update_content)
    
    return 'sample_update.txt'

if __name__ == "__main__":
    # 创建服务器实例
    server = UpdateServer(host='0.0.0.0', port=8080)  # 0.0.0.0允许所有IP访问
    
    # 添加示例公告
    sample_announcement = {
        "title": "重要通知",
        "content": "欢迎使用道衍AI浏览器局域网更新服务！\n\n最新功能：\n1. 支持多客户端连接\n2. 实时公告推送\n3. 自动更新检测",
        "version": "2.0"
    }
    server.save_announcement(sample_announcement)
    
    # 启动服务器
    server.start_server()
    
    try:
        # 保持主线程运行
        while True:
            pass
    except KeyboardInterrupt:
        print("\n正在停止服务器...")
        server.stop_server()
        print("服务器已停止")