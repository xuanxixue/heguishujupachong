import json
import requests
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLineEdit,
    QLabel, QMessageBox, QGroupBox, QComboBox, QSpinBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

class AIWorker(QThread):
    """AI工作线程，用于执行AI请求"""
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, api_url, api_key, model, prompt, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.prompt = prompt

    def run(self):
        try:
            headers = {
                "Content-Type": "application/json",
                # 修复API密钥中的多余字符和换行符
                "Authorization": f"Bearer {self.api_key.strip()}"
            }
            
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": self.prompt}],
                "temperature": 0.7
            }
            
            # 修复重复的/v1路径问题
            if self.api_url.endswith('/v1'):
                url = f"{self.api_url}/chat/completions"
            else:
                url = f"{self.api_url}/v1/chat/completions"
            
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                self.result_ready.emit(content)
            else:
                self.error_occurred.emit(f"API请求失败: {response.status_code} - {response.text}")
        except Exception as e:
            self.error_occurred.emit(f"发生错误: {str(e)}")

class AIChatDialog(QDialog):
    """AI聊天对话框"""
    
    def __init__(self, api_settings, parent=None):
        super().__init__(parent)
        self.api_settings = api_settings
        self.setWindowTitle("AI 聊天助手")
        self.resize(800, 600)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 聊天历史显示
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        
        # 用户输入
        input_layout = QHBoxLayout()
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("输入消息...")
        self.user_input.returnPressed.connect(self.send_message)
        
        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.send_message)
        
        input_layout.addWidget(self.user_input)
        input_layout.addWidget(self.send_btn)
        
        layout.addWidget(QLabel("AI 聊天记录:"))
        layout.addWidget(self.chat_history)
        layout.addLayout(input_layout)
        
    def send_message(self):
        user_message = self.user_input.text().strip()
        if not user_message:
            return
            
        # 显示用户消息
        self.chat_history.append(f"<b>你:</b> {user_message}")
        self.user_input.clear()
        self.send_btn.setEnabled(False)
        
        # 创建AI工作线程
        self.worker = AIWorker(
            self.api_settings["api_url"],
            self.api_settings["api_key"],
            self.api_settings["model"],
            user_message
        )
        self.worker.result_ready.connect(self.on_result_ready)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.finished.connect(lambda: self.send_btn.setEnabled(True))
        self.worker.start()
        
    def on_result_ready(self, result):
        self.chat_history.append(f"<b>AI助手:</b> {result}")
        self.chat_history.verticalScrollBar().setValue(
            self.chat_history.verticalScrollBar().maximum()
        )
        
    def on_error(self, error_msg):
        self.chat_history.append(f"<span style='color:red;'><b>错误:</b> {error_msg}</span>")
        self.send_btn.setEnabled(True)

class AISummaryDialog(QDialog):
    """AI网页总结对话框"""
    
    def __init__(self, api_settings, page_content, page_title, parent=None):
        super().__init__(parent)
        self.api_settings = api_settings
        self.page_content = page_content
        self.page_title = page_title
        self.setWindowTitle("AI 网页总结")
        self.resize(800, 600)
        self.setup_ui()
        self.summarize()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 标题显示
        title_label = QLabel(f"页面标题: {self.page_title}")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        # 总结结果显示
        self.summary_result = QTextEdit()
        self.summary_result.setReadOnly(True)
        
        layout.addWidget(title_label)
        layout.addWidget(QLabel("AI 总结结果:"))
        layout.addWidget(self.summary_result)
        
    def summarize(self):
        self.summary_result.setText("正在生成总结，请稍候...")
        
        prompt = f"请为以下网页内容生成一个简洁明了的总结:\n\n页面标题: {self.page_title}\n\n内容:\n{self.page_content[:3000]}..."
        
        # 创建AI工作线程
        self.worker = AIWorker(
            self.api_settings["api_url"],
            self.api_settings["api_key"],
            self.api_settings["model"],
            prompt
        )
        self.worker.result_ready.connect(self.on_summary_ready)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()
        
    def on_summary_ready(self, result):
        self.summary_result.setText(result)
        
    def on_error(self, error_msg):
        self.summary_result.setText(f"生成总结时出错: {error_msg}")