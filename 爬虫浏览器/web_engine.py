from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QMenu
# 添加导入
from PyQt5.QtWebEngineWidgets import QWebEngineSettings

class CustomWebEnginePage(QWebEnginePage):
    """自定义网页引擎页面，处理导航请求和新窗口请求"""
    
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self.navigation_attempts = {}

    def acceptNavigationRequest(self, url, navigation_type, isMainFrame):
        """处理导航请求，允许所有类型的导航"""
        # 记录导航尝试
        url_str = url.toString()
        self.navigation_attempts[url_str] = self.navigation_attempts.get(url_str, 0) + 1
        
        # 允许所有导航请求
        print(f"导航请求: {url_str}, 类型: {navigation_type}, 主框架: {isMainFrame}")
        return True

    def createWindow(self, type):
        """创建新窗口/新标签页 - 这是关键函数，处理新窗口请求"""
        print(f"创建新窗口请求: {type}")
        
        if self.main_window:
            # 在主窗口中创建新标签页
            new_browser = self.main_window.add_new_tab(QUrl("about:blank"), "新标签页")
            return new_browser.page()
        
        # 如果没有主窗口引用，创建一个新的浏览器窗口
        new_browser = QWebEngineView()
        new_page = CustomWebEnginePage(new_browser)
        new_browser.setPage(new_page)
        return new_page

    def triggerAction(self, action, checked=False):
        """重写triggerAction方法以添加自定义右键菜单项"""
        if action == QWebEnginePage.InspectElement:
            # 添加翻译选项到右键菜单
            menu = QMenu()
            translate_action = menu.addAction("🌐 翻译此页面")
            if self.main_window:
                translate_action.triggered.connect(self.main_window.translate_page)
            menu.addAction("检查元素")
            menu.exec_(self.view().mapToGlobal(self.view().pos()))
            return
        return super().triggerAction(action, checked)

    # 添加检查元素功能
    def inspect_element(self, position):
        """检查元素功能"""
        if self.main_window:
            self.main_window.open_dev_tools()
        self.triggerAction(QWebEnginePage.InspectElement)