# src/map_widget.py
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import pyqtSignal, Qt, QRectF, QPointF
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QBrush
import math

class MapWidget(QLabel):
    map_clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: #2d2d2d; border: 1px solid #555;")
        self.setText("暂无地图数据\n请先连接机器人并加载地图")
        self.setWordWrap(True)
        self.setScaledContents(False)

        self._bg_pixmap = None
        self.map_resolution = None
        self.map_origin_x = 0.0
        self.map_origin_y = 0.0
        self.map_img_width = 0
        self.map_img_height = 0

        self.scan_points = []

        self.robot_x = None
        self.robot_y = None
        self.robot_theta = 0.0

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
        self.map_resolution = meta.get("RESOLUTION", None)
        self.map_origin_x = meta.get("ORIGIN_X", 0.0)
        self.map_origin_y = meta.get("ORIGIN_Y", 0.0)

    def set_scan_points(self, points: list):
        self.scan_points = points
        self.update()

    def set_robot_pose(self, x: float, y: float, theta: float):
        self.robot_x = x
        self.robot_y = y
        self.robot_theta = theta
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        # 计算背景地图的缩放和偏移
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
            super().paintEvent(event)
            painter.end()
            return

        if self.map_resolution is None:
            painter.end()
            return

        origin_x = self.map_origin_x
        origin_y = self.map_origin_y
        resolution = self.map_resolution

        # 1. 绘制激光点云
        if self.scan_points:
            pen = QPen(QColor(0, 255, 0, 180))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            for lx, ly in self.scan_points:
                wx = lx
                wy = ly
                col = (wx - origin_x) / resolution
                row = self.map_img_height - (wy - origin_y) / resolution
                screen_x = offset_x + col * scale
                screen_y = offset_y + row * scale
                painter.drawPoint(int(screen_x), int(screen_y))

        # 2. 绘制机器人箭头
        if self.robot_x is not None and self.robot_y is not None:
            wx = self.robot_x
            wy = self.robot_y
            col = (wx - origin_x) / resolution
            row = self.map_img_height - (wy - origin_y) / resolution
            screen_x = offset_x + col * scale
            screen_y = offset_y + row * scale

            painter.save()
            painter.translate(screen_x, screen_y)
            # 屏幕坐标系 Y 轴向下，所以旋转角度取负数
            painter.rotate(-math.degrees(self.robot_theta)+90)
            arrow_size = 12
            points = [
                QPointF(0, -arrow_size),
                QPointF(-arrow_size/2, arrow_size/2),
                QPointF(arrow_size/2, arrow_size/2)
            ]
            pen_robot = QPen(QColor(255, 0, 0))
            pen_robot.setWidth(2)
            painter.setPen(pen_robot)
            brush_robot = QBrush(QColor(255, 0, 0, 150))
            painter.setBrush(brush_robot)
            painter.drawPolygon(*points)
            painter.restore()

        painter.end()