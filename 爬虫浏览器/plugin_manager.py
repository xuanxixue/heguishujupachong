import os
import sys
import zipfile
import shutil
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, 
    QTreeWidgetItem, QHeaderView, QFileDialog, QMessageBox, QLabel
)
from PyQt5.QtCore import Qt

class PluginManager(QDialog):
    """插件管理器"""
    
    def __init__(self, plugins, parent=None):
        super().__init__(parent)
        self.plugins = plugins
        self.setWindowTitle("插件管理器")
        self.setGeometry(300, 300, 800, 500)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("添加插件")
        self.remove_btn = QPushButton("移除插件")
        self.reload_btn = QPushButton("重新加载")

        self.add_btn.clicked.connect(self.add_plugin)
        self.remove_btn.clicked.connect(self.remove_plugin)
        self.reload_btn.clicked.connect(self.reload_plugins)

        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.remove_btn)
        toolbar.addWidget(self.reload_btn)
        toolbar.addStretch()

        # 插件列表
        self.plugins_list = QTreeWidget()
        self.plugins_list.setHeaderLabels(["插件名称", "版本", "描述"])
        self.plugins_list.header().setSectionResizeMode(0, QHeaderView.Stretch)

        layout.addLayout(toolbar)
        layout.addWidget(self.plugins_list)
        
        # 添加说明标签
        info_label = QLabel("插件目录: 程序目录下的 plugins 文件夹")
        info_label.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(info_label)
        
        self.refresh_list()

    def add_plugin(self):
        """添加插件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择插件文件", "", "插件文件 (*.zip *.py)"
        )
        
        if not file_path:
            return
            
        try:
            plugins_dir = "plugins"
            if not os.path.exists(plugins_dir):
                os.makedirs(plugins_dir)
                
            if file_path.endswith('.zip'):
                # 处理ZIP格式插件
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    # 获取插件名称（使用ZIP文件名，不含扩展名）
                    plugin_name = os.path.splitext(os.path.basename(file_path))[0]
                    plugin_dir = os.path.join(plugins_dir, plugin_name)
                    
                    # 创建插件目录
                    if not os.path.exists(plugin_dir):
                        os.makedirs(plugin_dir)
                    
                    # 解压文件
                    zip_ref.extractall(plugin_dir)
            else:
                # 处理单个Python文件插件
                plugin_name = os.path.splitext(os.path.basename(file_path))[0]
                plugin_dir = os.path.join(plugins_dir, plugin_name)
                
                # 创建插件目录
                if not os.path.exists(plugin_dir):
                    os.makedirs(plugin_dir)
                
                # 复制文件
                shutil.copy(file_path, os.path.join(plugin_dir, "main.py"))
            
            QMessageBox.information(self, "成功", "插件添加成功，请重新加载插件")
        except Exception as e:
            QMessageBox.critical(self, "失败", f"添加插件失败: {str(e)}")

    def remove_plugin(self):
        """移除插件"""
        current_item = self.plugins_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请选择要移除的插件")
            return
            
        plugin_name = current_item.text(0)
        
        reply = QMessageBox.question(
            self, "确认", f"确定要移除插件 '{plugin_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                plugin_path = os.path.join("plugins", plugin_name)
                if os.path.exists(plugin_path):
                    shutil.rmtree(plugin_path)
                QMessageBox.information(self, "成功", "插件移除成功，请重新加载插件")
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "失败", f"移除插件失败: {str(e)}")

    def reload_plugins(self):
        """重新加载插件"""
        if self.parent():
            self.parent().load_plugins()
        self.refresh_list()
        QMessageBox.information(self, "成功", "插件重新加载完成")

    def refresh_list(self):
        """刷新插件列表"""
        self.plugins_list.clear()
        
        plugins_dir = "plugins"
        if not os.path.exists(plugins_dir):
            return
            
        for plugin_name in os.listdir(plugins_dir):
            plugin_path = os.path.join(plugins_dir, plugin_name)
            if os.path.isdir(plugin_path):
                item = QTreeWidgetItem(self.plugins_list)
                item.setText(0, plugin_name)
                
                # 尝试读取插件信息
                try:
                    info_file = os.path.join(plugin_path, "plugin.json")
                    if os.path.exists(info_file):
                        import json
                        with open(info_file, 'r', encoding='utf-8') as f:
                            info = json.load(f)
                            item.setText(1, info.get("version", "未知"))
                            item.setText(2, info.get("description", "无描述"))
                    else:
                        item.setText(1, "未知")
                        item.setText(2, "无描述信息文件")
                except Exception:
                    item.setText(1, "未知")
                    item.setText(2, "信息读取失败")
                
                self.plugins_list.addTopLevelItem(item)