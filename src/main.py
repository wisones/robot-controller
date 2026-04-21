# src/main.py
import sys
from PyQt5.QtWidgets import QApplication
from main_window import MainWindow  # 直接导入同目录下的模块

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())