# src/map_widget.py
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen

class MapWidget(QLabel):
    """
    自定义地图显示控件
    支持：
    - 显示地图图片
    - 鼠标点击发送信号（后续用于设定导航点）
    - 实时绘制机器人位置（今天先预留接口）
    """
    # 信号：当鼠标在地图上点击时发送，参数为点击的像素坐标 (x, y)
    map_clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: #2d2d2d; border: 1px solid #555;")
        self.setText("暂无地图数据\n请先连接机器人并点击“获取当前地图”")
        self.setWordWrap(True)

        # 用于后续绘制机器人位置
        self.robot_x = None
        self.robot_y = None
        self.robot_theta = 0.0

    def mousePressEvent(self, event):
        """重写鼠标按下事件，发射点击信号"""
        if event.button() == Qt.LeftButton:
            # 获取点击位置（相对于控件）
            pos = event.pos()
            self.map_clicked.emit(pos.x(), pos.y())
        super().mousePressEvent(event)

    def set_map_pixmap(self, pixmap: QPixmap):
        """设置地图图片"""
        self.setPixmap(pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.setText("")  # 清除占位文字

    def set_robot_pose(self, x: float, y: float, theta: float):
        """
        设置机器人位置（像素坐标）
        今天只存储，不绘制，明天完善绘制逻辑
        """
        self.robot_x = x
        self.robot_y = y
        self.robot_theta = theta
        # 可以在这里触发重绘，但今天先不做
        # self.update()

    def paintEvent(self, event):
        """重绘事件，未来用于绘制机器人图标"""
        super().paintEvent(event)
        # 明天在这里添加绘制机器人的代码
        # if self.robot_x is not None and self.robot_y is not None:
        #     painter = QPainter(self)
        #     painter.setPen(QPen(QColor(255, 0, 0), 3))
        #     painter.drawEllipse(...)