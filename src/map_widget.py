# src/map_widget.py
import math
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import pyqtSignal, Qt, QRectF, QPointF
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont

class MapWidget(QLabel):
    # 信号：鼠标点击时发射像素坐标 (x, y)
    map_clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: #2d2d2d; border: 1px solid #555;")
        self.setText("暂无地图数据\n请先连接机器人并加载地图")
        self.setWordWrap(True)
        self.setScaledContents(False)   # 关闭自动缩放，我们自己绘制

        # ---------- 背景地图 ----------
        self._bg_pixmap = None          # QPixmap 原始地图图片
        self.map_img_width = 0          # 图像的像素尺寸
        self.map_img_height = 0

        # ---------- 地图元数据 ----------
        self.map_resolution = None      # 米/像素
        self.map_origin_x = 0.0         # 地图左下角世界坐标 X
        self.map_origin_y = 0.0         # 地图左下角世界坐标 Y

        # ---------- 激光扫描点云 ----------
        self.scan_points = []           # 每个元素为 (wx, wy) 世界坐标

        # ---------- 机器人位姿 ----------
        self.robot_x = None
        self.robot_y = None
        self.robot_theta = 0.0          # 弧度

        # ---------- 目标点 ----------
        self.goal_points = []           # 每个元素为 (wx, wy) 世界坐标

    # ==================== 鼠标事件 ====================
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            self.map_clicked.emit(pos.x(), pos.y())
        super().mousePressEvent(event)

    # ==================== 外部调用接口 ====================
    def set_map_from_bytes(self, data: bytes):
        """从二进制图片数据加载背景地图"""
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self._bg_pixmap = pixmap
            self.map_img_width = pixmap.width()
            self.map_img_height = pixmap.height()
            self.setText("")            # 清除占位文字
            self.update()
        else:
            # 加载失败保留原样
            pass

    def set_map_meta(self, meta: dict):
        """设置地图元数据：RESOLUTION, ORIGIN_X, ORIGIN_Y"""
        self.map_resolution = meta.get("RESOLUTION", None)
        self.map_origin_x = meta.get("ORIGIN_X", 0.0)
        self.map_origin_y = meta.get("ORIGIN_Y", 0.0)

    def set_scan_points(self, points: list):
        """设置激光扫描点云（世界坐标列表）"""
        self.scan_points = points
        self.update()

    def set_robot_pose(self, x: float, y: float, theta: float):
        """设置机器人位姿（世界坐标，弧度）"""
        self.robot_x = x
        self.robot_y = y
        self.robot_theta = theta
        self.update()

    def set_goal_points(self, points: list):
        """设置目标点列表，每个元素为 (wx, wy)"""
        self.goal_points = points
        self.update()

    # ==================== 核心绘制 ====================
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)   # 大量点不抗锯齿

        # 1. 计算背景地图的显示区域（等比缩放居中）
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
            # 没有地图时只绘制默认文字
            super().paintEvent(event)
            painter.end()
            return

        # 如果没有分辨率，无法继续绘制其他内容
        if self.map_resolution is None:
            painter.end()
            return

        # 常用变量
        resolution = self.map_resolution
        origin_x = self.map_origin_x
        origin_y = self.map_origin_y
        img_h = self.map_img_height

        # 2. 绘制激光点云（绿色）
        if self.scan_points:
            pen_scan = QPen(QColor(0, 255, 0, 180))
            pen_scan.setWidth(2)
            painter.setPen(pen_scan)
            painter.setBrush(Qt.NoBrush)
            for wx, wy in self.scan_points:
                col = (wx - origin_x) / resolution
                row = img_h - (wy - origin_y) / resolution
                sx = offset_x + col * scale
                sy = offset_y + row * scale
                painter.drawPoint(int(sx), int(sy))

        # 3. 绘制机器人箭头（红色）
        if self.robot_x is not None and self.robot_y is not None:
            wx = self.robot_x
            wy = self.robot_y
            col = (wx - origin_x) / resolution
            row = img_h - (wy - origin_y) / resolution
            sx = offset_x + col * scale
            sy = offset_y + row * scale

            painter.save()
            painter.translate(sx, sy)
            # 旋转：屏幕Y轴向下，需反向旋转并补偿90°使箭头默认指向右侧（地图X轴方向）
            painter.rotate(-math.degrees(self.robot_theta) + 90)

            # 箭头尺寸
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

        # 4. 绘制目标点（黄色圆点 + 序号）
        if self.goal_points:
            font = QFont()
            font.setBold(True)
            font.setPixelSize(12)
            painter.setFont(font)
            for i, (gx, gy) in enumerate(self.goal_points):
                col = (gx - origin_x) / resolution
                row = img_h - (gy - origin_y) / resolution
                sx = offset_x + col * scale
                sy = offset_y + row * scale

                # 实心圆
                pen_goal = QPen(QColor(255, 255, 0))
                pen_goal.setWidth(2)
                painter.setPen(pen_goal)
                painter.setBrush(QBrush(QColor(255, 255, 0, 100)))
                painter.drawEllipse(QPointF(sx, sy), 6, 6)

                # 序号
                painter.setPen(QColor(0, 0, 0))
                painter.drawText(int(sx) - 3, int(sy) - 8, str(i + 1))

        painter.end()