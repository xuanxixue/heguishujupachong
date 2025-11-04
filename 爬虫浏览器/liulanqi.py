import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QMessageBox
import requests

# 导入拆分的模块
from browser_main import ModernBrowser
from utils import SELENIUM_AVAILABLE, DOCX_AVAILABLE

# 确保插件目录在Python路径中
plugin_path = os.path.join(os.path.dirname(__file__), "plugins")
if plugin_path not in sys.path:
    sys.path.append(plugin_path)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))

    # 检查依赖提示
    missing = []
    for pkg, mod in [("requests", "requests"), ("bs4", "bs4")]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        QMessageBox.warning(None, "缺少依赖", f"请安装: pip install {' '.join(missing)}")

    if not SELENIUM_AVAILABLE:
        QMessageBox.information(None, "提示", "Selenium不可用 → 动态页面可能无法抓取")
    if not DOCX_AVAILABLE:
        QMessageBox.information(None, "提示", "DOCX导出功能不可用，请安装 python-docx")

    window = ModernBrowser()
    window.show()
    sys.exit(app.exec_())