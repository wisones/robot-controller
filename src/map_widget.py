# src/map_widget.py
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import pyqtSignal, Qt, QRectF, QPointF
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QBrush
import math

class MapWidget(QLabel):
    map_clicked = pyqtSignal(int, int)  # 像素坐标

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: #2d2d2d; border: 1px solid #555;")
        self.setText("暂无地图数据\n请先连接机器人并加载地图")
        self.setWordWrap(True)
        self.setScaledContents(False)

        # 背景地图
        self._bg_pixmap: QPixmap = None
        # 地图元数据
        self.map_resolution = None   # 米/像素
        self.map_origin_x = 0.0
        self.map_origin_y = 0.0
        self.map_img_width = 0
        self.map_img_height = 0

        # 激光扫描点云（世界坐标）
        self.scan_points = []

        # 机器人位姿（世界坐标系）
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.robot_theta = 0.0   # 弧度

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            self.map_clicked.emit(pos.x(), pos.y())
        super().mousePressEvent(event)

    def set_map_from_bytes(self, data: bytes):
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self._bg_pixmap = pixmap
            self.map_img_width = pixmap.width()
            self.map_img_height = pixmap.height()
            self.setText("")
            self.update()
        else:
            pass

    def set_map_meta(self, meta: dict):
        """设置地图元数据：RESOLUTION, ORIGIN_X, ORIGIN_Y"""
        self.map_resolution = meta.get("RESOLUTION", None)
        self.map_origin_x = meta.get("ORIGIN_X", 0.0)
        self.map_origin_y = meta.get("ORIGIN_Y", 0.0)
        # 地图尺寸由图片决定，不需要从元数据获取

    def set_scan_points(self, points: list):
        """激光扫描点（激光坐标系，x向前，y向左，单位米）"""
        self.scan_points = points
        self.update()

    def set_robot_pose(self, x: float, y: float, theta: float):
        self.robot_x = x
        self.robot_y = y
        self.robot_theta = theta
        # 当机器人位置更新时，可以触发重绘以反映变化（如果不订阅扫描也会重绘）
        # self.update()  # 如果需要实时位置标记，可打开

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        # 绘制背景地图（居中缩放）
        scale = 1.0
        offset_x = 0.0
        offset_y = 0.0
        if self._bg_pixmap and self.map_img_width > 0:
            widget_w = self.width()
            widget_h = self.height()
            img_w = self.map_img_width
            img_h = self.map_img_height
            scale = min(widget_w / img_w, widget_h / img_h)
            scaled_w = img_w * scale
            scaled_h = img_h * scale
            offset_x = (widget_w - scaled_w) / 2.0
            offset_y = (widget_h - scaled_h) / 2.0
            target_rect = QRectF(offset_x, offset_y, scaled_w, scaled_h)
            painter.drawPixmap(target_rect, self._bg_pixmap, QRectF(0, 0, img_w, img_h))
        else:
            # 没有地图时，清屏文字保留
            super().paintEvent(event)
            painter.end()
            return

        # 绘制激光点云
        if not self.scan_points:
            painter.end()
            return
        if self.map_resolution is None:
            painter.end()
            return

        # 坐标转换参数
        origin_x = self.map_origin_x
        origin_y = self.map_origin_y
        resolution = self.map_resolution

        # 机器人位姿
        rx = self.robot_x
        ry = self.robot_y
        rtheta = self.robot_theta
        cos_th = math.cos(rtheta)
        sin_th = math.sin(rtheta)

        pen = QPen(QColor(0, 255, 0, 180))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # 绘制激光点云（假设点云已经是世界坐标系，x向右，y向上？需要根据地图坐标系微调）
        for lx, ly in self.scan_points:
            # 直接使用 lx, ly 作为世界坐标 wx, wy
            wx = lx
            wy = ly
            col = (wx - origin_x) / resolution
            row = self.map_img_height - (wy - origin_y) / resolution
            screen_x = offset_x + col * scale
            screen_y = offset_y + row * scale
            painter.drawPoint(int(screen_x), int(screen_y))

        painter.end()