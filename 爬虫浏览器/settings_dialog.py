import json
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, 
    QLineEdit, QCheckBox, QDialogButtonBox, QFileDialog, QLabel,
    QComboBox, QSpinBox
)
from PyQt5.QtCore import QStandardPaths

class SettingsDialog(QDialog):
    """设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("浏览器设置")
        self.setGeometry(400, 400, 600, 500)
        self.settings_file = "settings.json"
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 下载设置
        download_group = QGroupBox("下载设置")
        download_layout = QVBoxLayout()
        
        self.download_path_edit = QLineEdit()
        self.download_path_edit.setText(QStandardPaths.writableLocation(QStandardPaths.DownloadLocation))
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_download_path)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("下载路径:"))
        path_layout.addWidget(self.download_path_edit)
        path_layout.addWidget(self.browse_btn)
        
        self.ask_save_check = QCheckBox("每次下载前询问保存位置")
        self.ask_save_check.setChecked(True)
        
        download_layout.addLayout(path_layout)
        download_layout.addWidget(self.ask_save_check)
        download_group.setLayout(download_layout)

        # 隐私设置
        privacy_group = QGroupBox("隐私设置")
        privacy_layout = QVBoxLayout()
        
        self.clear_on_exit = QCheckBox("退出时清除浏览数据")
        self.block_images = QCheckBox("阻止图片加载（加速浏览）")
        self.javascript_enabled = QCheckBox("启用JavaScript")
        self.javascript_enabled.setChecked(True)
        
        privacy_layout.addWidget(self.clear_on_exit)
        privacy_layout.addWidget(self.block_images)
        privacy_layout.addWidget(self.javascript_enabled)
        privacy_group.setLayout(privacy_layout)

        # AI 设置
        self.ai_group = QGroupBox("AI 设置")
        ai_layout = QVBoxLayout()
        
        self.ai_api_url = QLineEdit()
        self.ai_api_url.setPlaceholderText("例如: https://api.openai.com")
        
        self.ai_api_key = QLineEdit()
        self.ai_api_key.setEchoMode(QLineEdit.Password)
        self.ai_api_key.setPlaceholderText("输入API密钥")
        
        self.ai_model = QComboBox()
        # 添加更多AI模型选项，包括DeepSeek、Kimi、通义千问等
        self.ai_model.addItems([
            "gpt-3.5-turbo", 
            "gpt-4", 
            "gpt-4-turbo",
            "claude-2", 
            "claude-3-opus",
            "llama2",
            "llama3",
            "deepseek-chat",     # DeepSeek
            "deepseek-coder",    # DeepSeek
            "moonshot-v1-8k",    # Kimi
            "moonshot-v1-32k",   # Kimi
            "moonshot-v1-128k",  # Kimi
            "qwen-turbo",        # 通义千问
            "qwen-plus",         # 通义千问
            "qwen-max",          # 通义千问
            "yi-34b-chat-0205",  # 零一万物
            "yi-34b-chat-200k"   # 零一万物
        ])
        self.ai_model.setEditable(True)
        
        ai_layout.addWidget(QLabel("API URL:"))
        ai_layout.addWidget(self.ai_api_url)
        ai_layout.addWidget(QLabel("API 密钥:"))
        ai_layout.addWidget(self.ai_api_key)
        ai_layout.addWidget(QLabel("模型:"))
        ai_layout.addWidget(self.ai_model)
        
        self.ai_group.setLayout(ai_layout)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)

        layout.addWidget(download_group)
        layout.addWidget(privacy_group)
        layout.addWidget(self.ai_group)
        layout.addStretch()
        layout.addWidget(button_box)

    def browse_download_path(self):
        """选择下载路径"""
        path = QFileDialog.getExistingDirectory(self, "选择下载文件夹", self.download_path_edit.text())
        if path:
            self.download_path_edit.setText(path)
            
    def save_settings(self):
        """保存设置到文件"""
        settings = {
            "download_path": self.download_path_edit.text(),
            "ask_before_download": self.ask_save_check.isChecked(),
            "clear_on_exit": self.clear_on_exit.isChecked(),
            "block_images": self.block_images.isChecked(),
            "javascript_enabled": self.javascript_enabled.isChecked(),
            "ai_api_url": self.ai_api_url.text(),
            "ai_api_key": self.ai_api_key.text(),
            "ai_model": self.ai_model.currentText()
        }
        
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法保存设置: {e}")
            
    def load_settings(self):
        """从文件加载设置"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    
                self.download_path_edit.setText(settings.get("download_path", ""))
                self.ask_save_check.setChecked(settings.get("ask_before_download", True))
                self.clear_on_exit.setChecked(settings.get("clear_on_exit", False))
                self.block_images.setChecked(settings.get("block_images", False))
                self.javascript_enabled.setChecked(settings.get("javascript_enabled", True))
                self.ai_api_url.setText(settings.get("ai_api_url", ""))
                self.ai_api_key.setText(settings.get("ai_api_key", ""))
                model = settings.get("ai_model", "gpt-3.5-turbo")
                if self.ai_model.findText(model) == -1:
                    self.ai_model.addItem(model)
                self.ai_model.setCurrentText(model)
            except Exception as e:
                print(f"加载设置失败: {e}")