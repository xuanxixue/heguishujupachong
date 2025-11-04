from PyQt5.QtWidgets import QAction, QMessageBox

class Plugin:
    def __init__(self, browser):
        self.browser = browser
        self.action = None

    def init(self):
        """初始化插件"""
        # 添加菜单项
        self.action = QAction("示例插件功能", self.browser)
        self.action.triggered.connect(self.do_something)
        
        # 添加到工具菜单
        tools_menu = None
        for action in self.browser.menuBar().actions():
            if action.text() == "工具":
                tools_menu = action.menu()
                break
                
        if tools_menu:
            tools_menu.addAction(self.action)

    def do_something(self):
        """执行插件功能"""
        QMessageBox.information(
            self.browser, 
            "示例插件", 
            "这是一个示例插件功能！\n插件系统工作正常。"
        )

    def cleanup(self):
        """清理插件"""
        if self.action:
            self.action.setParent(None)