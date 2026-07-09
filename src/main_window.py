# src/main_window.py
import math, time, sys, os, base64
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QGroupBox, QLabel, QStatusBar, QSplitter,
    QLineEdit, QFormLayout
)
from PyQt5.QtGui import QIcon
from map_widget import MapWidget
from tcp_client import RobotTCPClient
from spray_controller import SprayController
from report_controller import ReportController
import socket
import struct


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("鸡舍消毒机器人控制终端")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)

        # 窗口图标（兼容打包与源码运行）
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_path, "resources", "images", "robot_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # ---------- 地图元数据 ----------
        self.map_meta = None
        self.current_map_name = ""

        # ---------- 目标点 & 导航 ----------
        self.goal_points = []
        self.navi_queue = []
        self.current_navi_index = 0
        self.nav_state = 'idle'
        self.fail_count = 0

        # ---------- 机器人位姿 & 速度 ----------
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.latest_theta = 0.0
        self.last_pose_time = None
        self.last_pose_x = None
        self.last_pose_y = None
        self.current_speed = 0.0

        # ---------- 主界面 ----------
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        self.map_widget = MapWidget()
        self.map_widget.map_clicked.connect(self.on_map_clicked)
        self.map_widget.mouse_moved.connect(self.on_mouse_moved)

        right_panel = self.create_right_panel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.map_widget)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        # ---------- 状态栏 ----------
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 | 未连接机器人")

        # ---------- 通信对象 ----------
        self.tcp_client = RobotTCPClient()

        self.spray_controller = SprayController(esp_ip="192.168.10.200")
        self.spray_controller.connection_error.connect(self.on_spray_error)
        self.spray_controller.status_message.connect(self.on_spray_status)
        self.spray_controller.left_water_updated.connect(self.on_left_water_updated)
        self.spray_controller.right_water_updated.connect(self.on_right_water_updated)
        self.spray_controller.connected.connect(lambda: self.status_bar.showMessage("喷雾控制器已连接"))
        self.spray_controller.disconnected.connect(lambda: self.status_bar.showMessage("喷雾控制器已断开，正在后台重连..."))
        self.spray_controller.command_started.connect(self.on_spray_command_started)
        self.spray_controller.command_finished.connect(self.on_spray_command_finished)

        self.report_controller = ReportController()
        self.report_controller.status_changed.connect(self.on_report_status)
        self.report_controller.connection_ok.connect(self.on_report_connected)
        self.report_controller.connection_failed.connect(self.on_report_failed)

        self.init_tcp_signals()
        self.init_ui_connections()

        self.battery_timer = QTimer(self)
        self.battery_timer.timeout.connect(self._query_battery)
        self.battery_timer.start(30000)

        self.edit_ip.setText("192.168.10.159")
        self.edit_port.setText("10000")

    # ==================== 定时任务 ====================
    def _query_battery(self):
        if self.tcp_client.is_connected:
            self.tcp_client.send_command({"CMD": "CMD_GET_BATTERY"})

    # ==================== UI 布局 ====================
    def create_right_panel(self) -> QWidget:
        panel = QWidget()
        main_layout = QHBoxLayout(panel)
        main_layout.setSpacing(10)

        # ---- 左侧列：底盘连接、地图控制、顺序导航、连接状态 ----
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setSpacing(10)

        # 底盘连接
        conn_group = QGroupBox("底盘连接")
        conn_layout = QFormLayout(conn_group)
        self.edit_ip = QLineEdit()
        self.edit_ip.setPlaceholderText("例如: 192.168.1.120")
        conn_layout.addRow("IP 地址:", self.edit_ip)
        self.edit_port = QLineEdit()
        self.edit_port.setPlaceholderText("例如: 9090")
        conn_layout.addRow("端口:", self.edit_port)

        btn_conn_layout = QHBoxLayout()
        self.btn_connect = QPushButton("连接")
        self.btn_connect.setMinimumHeight(30)
        self.btn_ping = QPushButton("Ping 测试")
        self.btn_ping.setMinimumHeight(30)
        btn_conn_layout.addWidget(self.btn_connect)
        btn_conn_layout.addWidget(self.btn_ping)
        conn_layout.addRow(btn_conn_layout)

        # 地图控制
        map_group = QGroupBox("地图控制")
        map_layout = QVBoxLayout(map_group)
        self.btn_get_map = QPushButton("获取静态地图")
        self.btn_get_map.setMinimumHeight(35)
        self.btn_sub_scan = QPushButton("订阅激光扫描")
        self.btn_sub_scan.setMinimumHeight(35)
        self.btn_sub_scan.setCheckable(True)
        self.btn_show_pose = QPushButton("显示当前位置")
        self.btn_show_pose.setMinimumHeight(35)
        map_layout.addWidget(self.btn_get_map)
        map_layout.addWidget(self.btn_sub_scan)
        map_layout.addWidget(self.btn_show_pose)
        map_group.setLayout(map_layout)

        # 顺序导航
        navi_group = QGroupBox("顺序导航")
        navi_layout = QVBoxLayout(navi_group)
        self.btn_add_goal = QPushButton("添加目标点")
        self.btn_add_goal.setMinimumHeight(35)
        self.btn_add_goal.setCheckable(True)
        self.btn_clear_goals = QPushButton("清空目标点")
        self.btn_clear_goals.setMinimumHeight(35)
        self.btn_start_navi = QPushButton("开始顺序导航")
        self.btn_start_navi.setMinimumHeight(35)
        self.btn_cancel_navi = QPushButton("停止导航")
        self.btn_cancel_navi.setMinimumHeight(35)
        navi_layout.addWidget(self.btn_add_goal)
        navi_layout.addWidget(self.btn_clear_goals)
        navi_layout.addWidget(self.btn_start_navi)
        navi_layout.addWidget(self.btn_cancel_navi)

        # 手动输入坐标
        coord_group = QGroupBox("坐标输入")
        coord_layout = QVBoxLayout(coord_group)
        
        coord_input_layout = QHBoxLayout()
        coord_input_layout.addWidget(QLabel("X:"))
        self.edit_coord_x = QLineEdit()
        self.edit_coord_x.setPlaceholderText("X坐标")
        self.edit_coord_x.setMaximumWidth(100)
        coord_input_layout.addWidget(self.edit_coord_x)
        
        coord_input_layout.addWidget(QLabel("Y:"))
        self.edit_coord_y = QLineEdit()
        self.edit_coord_y.setPlaceholderText("Y坐标")
        self.edit_coord_y.setMaximumWidth(100)
        coord_input_layout.addWidget(self.edit_coord_y)
        coord_layout.addLayout(coord_input_layout)
        
        self.btn_add_coord = QPushButton("添加坐标点")
        self.btn_add_coord.setMinimumHeight(35)
        coord_layout.addWidget(self.btn_add_coord)

        # 连接状态
        status_group = QGroupBox("连接状态")
        status_layout = QVBoxLayout(status_group)
        self.label_conn_status = QLabel("未连接")
        self.label_conn_status.setStyleSheet("color: orange; font-weight: bold;")

        self.speed_label = QLabel("运动速度: --- m/s")
        self.battery_label = QLabel("电量: --- %")

        status_layout.addWidget(self.label_conn_status)
        status_layout.addWidget(self.speed_label)
        status_layout.addWidget(self.battery_label)

        left_layout.addWidget(conn_group)
        left_layout.addWidget(map_group)
        left_layout.addWidget(navi_group)
        left_layout.addWidget(coord_group)
        left_layout.addWidget(status_group)
        left_layout.addStretch()

        # ---- 右侧列：喷雾控制、指挥中心 ----
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setSpacing(10)

        # 左侧喷雾 + 水量
        spray_left_group = QGroupBox("左侧喷雾")
        spray_left_layout = QVBoxLayout(spray_left_group)

        btn_left_layout = QHBoxLayout()
        self.btn_spray_left_on = QPushButton("开启")
        self.btn_spray_left_on.setMinimumHeight(40)
        self.btn_spray_left_on.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        self.btn_spray_left_off = QPushButton("关闭")
        self.btn_spray_left_off.setMinimumHeight(40)
        self.btn_spray_left_off.setStyleSheet(
            "background-color: #f44336; color: white; font-weight: bold;"
        )
        btn_left_layout.addWidget(self.btn_spray_left_on)
        btn_left_layout.addWidget(self.btn_spray_left_off)

        self.left_water_label = QLabel("水量: --- %")
        calib_left_layout = QHBoxLayout()
        self.btn_left_tare = QPushButton("液面校准")
        self.btn_left_tare.setMinimumWidth(80)
        self.btn_left_full = QPushButton("设满")
        self.btn_left_full.setMinimumWidth(60)
        calib_left_layout.addWidget(self.left_water_label)
        calib_left_layout.addStretch()
        calib_left_layout.addWidget(self.btn_left_tare)
        calib_left_layout.addWidget(self.btn_left_full)

        spray_left_layout.addLayout(btn_left_layout)
        spray_left_layout.addLayout(calib_left_layout)

        # 右侧喷雾 + 水量
        spray_right_group = QGroupBox("右侧喷雾")
        spray_right_layout = QVBoxLayout(spray_right_group)

        btn_right_layout = QHBoxLayout()
        self.btn_spray_right_on = QPushButton("开启")
        self.btn_spray_right_on.setMinimumHeight(40)
        self.btn_spray_right_on.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        self.btn_spray_right_off = QPushButton("关闭")
        self.btn_spray_right_off.setMinimumHeight(40)
        self.btn_spray_right_off.setStyleSheet(
            "background-color: #f44336; color: white; font-weight: bold;"
        )
        btn_right_layout.addWidget(self.btn_spray_right_on)
        btn_right_layout.addWidget(self.btn_spray_right_off)

        self.right_water_label = QLabel("水量: --- %")
        calib_right_layout = QHBoxLayout()
        self.btn_right_tare = QPushButton("液面校准")
        self.btn_right_tare.setMinimumWidth(80)
        self.btn_right_full = QPushButton("设满")
        self.btn_right_full.setMinimumWidth(60)
        calib_right_layout.addWidget(self.right_water_label)
        calib_right_layout.addStretch()
        calib_right_layout.addWidget(self.btn_right_tare)
        calib_right_layout.addWidget(self.btn_right_full)

        spray_right_layout.addLayout(btn_right_layout)
        spray_right_layout.addLayout(calib_right_layout)

        # 指挥中心上报
        report_group = QGroupBox("指挥中心")
        report_layout = QFormLayout(report_group)
        self.edit_server_url = QLineEdit()
        self.edit_server_url.setPlaceholderText("http://192.168.1.100:5000/api/robot/status")
        self.edit_server_url.setText("http://127.0.0.1:5000/api/robot/status")
        report_layout.addRow("服务器URL:", self.edit_server_url)
        self.edit_device_id = QLineEdit()
        self.edit_device_id.setPlaceholderText("robot_001")
        self.edit_device_id.setText("robot_001")
        report_layout.addRow("设备ID:", self.edit_device_id)

        btn_report_layout = QHBoxLayout()
        self.btn_report_connect = QPushButton("连接")
        self.btn_report_connect.setMinimumHeight(30)
        self.btn_report_test = QPushButton("测试连接")
        self.btn_report_test.setMinimumHeight(30)
        btn_report_layout.addWidget(self.btn_report_connect)
        btn_report_layout.addWidget(self.btn_report_test)
        report_layout.addRow(btn_report_layout)

        self.label_report_status = QLabel("未连接")
        self.label_report_status.setStyleSheet("color: orange; font-weight: bold;")
        report_layout.addRow("状态:", self.label_report_status)

        right_layout.addWidget(spray_left_group)
        right_layout.addWidget(spray_right_group)
        right_layout.addWidget(report_group)
        right_layout.addStretch()

        main_layout.addWidget(left_column)
        main_layout.addWidget(right_column)
        return panel

    # ==================== 信号连接 ====================
    def init_ui_connections(self):
        self.btn_connect.clicked.connect(self.on_connect)
        self.btn_ping.clicked.connect(self.on_ping)
        self.btn_get_map.clicked.connect(self.on_get_map)
        self.btn_sub_scan.toggled.connect(self.on_sub_scan_toggled)
        self.btn_show_pose.clicked.connect(self.on_show_pose)
        self.btn_add_goal.toggled.connect(self.on_add_goal_toggled)
        self.btn_clear_goals.clicked.connect(self.on_clear_goals)
        self.btn_start_navi.clicked.connect(self.on_start_navi)
        self.btn_cancel_navi.clicked.connect(self.on_cancel_navi)
        self.btn_add_coord.clicked.connect(self.on_add_coord_clicked)
        self.btn_spray_left_on.clicked.connect(self.on_spray_left_on)
        self.btn_spray_left_off.clicked.connect(self.on_spray_left_off)
        self.btn_spray_right_on.clicked.connect(self.on_spray_right_on)
        self.btn_spray_right_off.clicked.connect(self.on_spray_right_off)
        self.btn_left_tare.clicked.connect(self.spray_controller.tare_left)
        self.btn_left_full.clicked.connect(self.spray_controller.set_left_full)
        self.btn_right_tare.clicked.connect(self.spray_controller.tare_right)
        self.btn_right_full.clicked.connect(self.spray_controller.set_right_full)
        self.btn_report_connect.clicked.connect(self.on_report_connect)
        self.btn_report_test.clicked.connect(self.on_report_test)

    def init_tcp_signals(self):
        self.tcp_client.connected.connect(self.on_tcp_connected)
        self.tcp_client.disconnected.connect(self.on_tcp_disconnected)
        self.tcp_client.error_occurred.connect(self.on_tcp_error)
        self.tcp_client.response_received.connect(self.on_response_received)
        self.tcp_client.scan_received.connect(self.on_scan_received)
        self.tcp_client.pose_received.connect(self.on_pose_received)
        self.tcp_client.navi_received.connect(self.on_navi_received)

    # ==================== TCP 回调 ====================
    def on_tcp_connected(self):
        self.label_conn_status.setText("已连接")
        self.label_conn_status.setStyleSheet("color: green; font-weight: bold;")
        self.status_bar.showMessage("底盘连接成功，自动订阅位置...")
        self.tcp_client.send_command({"CMD": "CMD_SUB_POSE"})
        self.report_controller.set_tcp_connected(True)

    def on_tcp_disconnected(self):
        self.label_conn_status.setText("未连接")
        self.label_conn_status.setStyleSheet("color: orange; font-weight: bold;")
        self.status_bar.showMessage("底盘连接已断开")
        self.report_controller.set_tcp_connected(False)

    def on_tcp_error(self, err_msg: str):
        print(f"[TCP 错误] {err_msg}")
        self.status_bar.showMessage(f"错误: {err_msg}")

    # ==================== 通用响应处理 ====================
    def on_response_received(self, data: dict):
        cmd = data.get("CMD", "")
        if cmd == "CMD_GET_VERSION":
            self.status_bar.showMessage(f"版本: {data.get('VERSION', '未知')}")
        elif cmd == "CMD_GET_CURRENT_MAP_CONFIG":
            map_config = data.get("MAP_CURRENT_CONFIG", {})
            map_name = map_config.get("STATIC_MAP_NAME", "")
            if map_name:
                self.current_map_name = map_name
                self.status_bar.showMessage(f"当前地图: {map_name}，正在获取元数据...")
                self.tcp_client.send_command({"CMD": "CMD_GET_MAP_META_DATA", "MAP_NAME": map_name})
            else:
                self.status_bar.showMessage("未找到地图名称")
        elif cmd == "CMD_GET_MAP_META_DATA":
            self.map_meta = data.get("MAP_META_DATA", {})
            self.map_widget.set_map_meta(self.map_meta)
            self.status_bar.showMessage("元数据已获取，正在下载地图...")
            if self.current_map_name:
                self.tcp_client.send_command({"CMD": "CMD_GET_MAP_DATA", "MAP_NAME": self.current_map_name})
        elif cmd == "CMD_GET_MAP_DATA":
            map_data_b64 = data.get("MAP_DATA", "")
            if map_data_b64:
                self.display_map(map_data_b64)
                self.status_bar.showMessage("地图加载成功")
        elif cmd == "CMD_GET_BATTERY":
            battery = data.get("battery", None)
            if battery is not None:
                self.battery_label.setText(f"电量: {battery} %")
                self.report_controller.update_battery(battery)

    # ==================== 地图 / 点云 / 位置 ====================
    def on_get_map(self):
        if not self.tcp_client.is_connected: return
        self.status_bar.showMessage("正在获取地图配置...")
        self.tcp_client.send_command({"CMD": "CMD_GET_CURRENT_MAP_CONFIG"})

    def display_map(self, b64_data: str):
        try:
            img_bytes = base64.b64decode(b64_data)
            self.map_widget.set_map_from_bytes(img_bytes)
        except Exception as e:
            self.status_bar.showMessage(f"地图解码失败: {str(e)}")

    def on_sub_scan_toggled(self, checked: bool):
        if not self.tcp_client.is_connected:
            self.btn_sub_scan.setChecked(False)
            return
        if checked:
            self.tcp_client.send_command({"CMD": "CMD_SUB_SCAN"})
        else:
            self.tcp_client.send_command({"CMD": "CMD_CANCEL_SUB_SCAN"})

    def on_scan_received(self, data: dict):
        b64_data = data.get("LASER_SCAN", "")
        if not b64_data: return
        try:
            raw = base64.b64decode(b64_data)
            points = []
            for i in range(0, len(raw), 12):
                if i + 12 > len(raw): break
                x, y, z = struct.unpack('<fff', raw[i:i+12])
                points.append((x, y))
            self.map_widget.set_scan_points(points)
        except Exception as e:
            self.status_bar.showMessage(f"点云解析错误: {e}")

    def on_pose_received(self, data: dict):
        pose = data.get("ROBOT_POSE", None)
        if pose:
            x = pose.get("X", 0.0)
            y = pose.get("Y", 0.0)
            theta = pose.get("THETA", 0.0)
            self.map_widget.set_robot_pose(x, y, theta)

            now = time.time()
            if self.last_pose_time and self.last_pose_x is not None:
                dt = now - self.last_pose_time
                if dt > 0.001:
                    dx = x - self.last_pose_x
                    dy = y - self.last_pose_y
                    dist = math.sqrt(dx*dx + dy*dy)
                    self.current_speed = dist / dt
                    self.speed_label.setText(f"运动速度: {self.current_speed:.2f} m/s")
            self.last_pose_time = now
            self.last_pose_x = x
            self.last_pose_y = y
            self.robot_x = x
            self.robot_y = y
            self.latest_theta = theta

    def on_show_pose(self):
        self.status_bar.showMessage("位置实时显示中")

    def on_mouse_moved(self, wx: float, wy: float):
        """鼠标悬停时显示世界坐标"""
        self.status_bar.showMessage(f"鼠标位置: X={wx:.2f}, Y={wy:.2f}")

    # ==================== 导航相关 ====================
    def on_add_goal_toggled(self, checked: bool):
        if checked:
            self.status_bar.showMessage("在地图上点击添加目标点")
        else:
            self.status_bar.showMessage("已退出添加模式")

    def on_map_clicked(self, x: int, y: int):
        if not self.btn_add_goal.isChecked(): return
        if not self.map_meta or not self.map_widget._bg_pixmap:
            self.status_bar.showMessage("请先加载地图")
            return

        widget_w = self.map_widget.width()
        widget_h = self.map_widget.height()
        img_w = self.map_widget.map_img_width
        img_h = self.map_widget.map_img_height
        scale = min(widget_w / img_w, widget_h / img_h)
        offset_x = (widget_w - img_w * scale) / 2.0
        offset_y = (widget_h - img_h * scale) / 2.0

        col = (x - offset_x) / scale
        row = (y - offset_y) / scale
        resolution = self.map_meta["RESOLUTION"]
        origin_x = self.map_meta["ORIGIN_X"]
        origin_y = self.map_meta["ORIGIN_Y"]
        wx = col * resolution + origin_x
        wy = (img_h - row) * resolution + origin_y

        self.goal_points.append((wx, wy))
        self.map_widget.set_goal_points(self.goal_points)
        self.status_bar.showMessage(f"已添加 {len(self.goal_points)} 个目标点")

    def on_clear_goals(self):
        self.goal_points.clear()
        self.map_widget.set_goal_points([])
        self.status_bar.showMessage("目标点已清空")
        if self.nav_state != 'idle':
            self.on_cancel_navi()

    def on_add_coord_clicked(self):
        """手动输入坐标添加目标点"""
        try:
            wx = float(self.edit_coord_x.text())
            wy = float(self.edit_coord_y.text())
        except ValueError:
            self.status_bar.showMessage("请输入有效的坐标值")
            return
        
        self.goal_points.append((wx, wy))
        self.map_widget.set_goal_points(self.goal_points)
        self.edit_coord_x.clear()
        self.edit_coord_y.clear()
        self.status_bar.showMessage(f"已添加 {len(self.goal_points)} 个目标点")

    def on_start_navi(self):
        if not self.tcp_client.is_connected:
            self.status_bar.showMessage("请先连接底盘")
            return
        if not self.goal_points:
            self.status_bar.showMessage("请先添加目标点")
            return
        if self.nav_state != 'idle':
            self.status_bar.showMessage("导航已在运行中")
            return

        self.navi_queue = []
        for i, (wx, wy) in enumerate(self.goal_points):
            if i + 1 < len(self.goal_points):
                nx, ny = self.goal_points[i + 1]
                dx = nx - wx
                dy = ny - wy
                theta = math.atan2(dy, dx)
            else:
                if i > 0:
                    px, py = self.goal_points[i - 1]
                    dx = wx - px
                    dy = wy - py
                    theta = math.atan2(dy, dx)
                else:
                    theta = 0.0
            self.navi_queue.append((wx, wy, theta))

        self.current_navi_index = 0
        self.nav_state = 'navigating'
        self.fail_count = 0
        self.tcp_client.send_command({"CMD": "CMD_SUB_NAVI"})
        self._send_next_goal()

    def _send_next_goal(self):
        if self.current_navi_index >= len(self.navi_queue):
            self._finish_navigation()
            return
        if self.fail_count > len(self.navi_queue):
            self.status_bar.showMessage("连续导航失败次数过多，终止")
            self._finish_navigation()
            return
        wx, wy, theta = self.navi_queue[self.current_navi_index]
        self.tcp_client.send_command({"CMD": "CMD_NAV_BY_POSE2D", "X": wx, "Y": wy, "THETA": theta})
        self.status_bar.showMessage(f"前往目标点 {self.current_navi_index+1}/{len(self.navi_queue)}")

    def _finish_navigation(self):
        self.nav_state = 'idle'
        self.navi_queue.clear()
        self.current_navi_index = 0
        self.fail_count = 0
        self.status_bar.showMessage("顺序导航完成")

    def on_navi_received(self, data: dict):
        if self.nav_state != 'navigating': return
        navi_info = data.get("NAVI_INFO", {})
        status = navi_info.get("TASK_STATUS", "")
        if status == "COMPLETED":
            self.fail_count = 0
            self.current_navi_index += 1
            self._send_next_goal()
        elif status == "NAV_FAIL":
            self.fail_count += 1
            self.status_bar.showMessage(f"目标点 {self.current_navi_index+1} 失败，跳过")
            self.current_navi_index += 1
            self._send_next_goal()
        elif status == "CANCELLED":
            self.status_bar.showMessage("导航被取消")
            self.nav_state = 'idle'
            self.navi_queue.clear()
            self.fail_count = 0

    def on_cancel_navi(self):
        if self.nav_state != 'idle':
            self.tcp_client.send_command({"CMD": "CMD_NAV_CANCEL"})
        self.nav_state = 'idle'
        self.navi_queue.clear()
        self.current_navi_index = 0
        self.fail_count = 0
        self.status_bar.showMessage("导航已取消")

    # ==================== 连接 / Ping ====================
    def on_connect(self):
        ip = self.edit_ip.text().strip() or "192.168.10.159"
        port_text = self.edit_port.text().strip() or "10000"
        try:
            port = int(port_text)
        except ValueError:
            self.status_bar.showMessage("端口号必须是数字")
            return
        self.status_bar.showMessage(f"正在连接 {ip}:{port} ...")
        self.tcp_client.connect_to_robot(ip, port)

    def on_ping(self):
        if not self.tcp_client.is_connected:
            self.status_bar.showMessage("请先连接底盘")
            return
        self.status_bar.showMessage("Ping 测试中...")
        self.tcp_client.send_command({"CMD": "CMD_GET_VERSION"})

    # ==================== 喷雾开关 ====================
    def on_spray_left_on(self):   self.spray_controller.left_on()
    def on_spray_left_off(self):  self.spray_controller.left_off()
    def on_spray_right_on(self):  self.spray_controller.right_on()
    def on_spray_right_off(self): self.spray_controller.right_off()

    def on_spray_error(self, msg: str):
        self.status_bar.showMessage(f"喷雾错误: {msg}")

    def on_spray_status(self, msg: str):
        self.status_bar.showMessage(msg)

    # ==================== 水位更新 ====================
    def on_left_water_updated(self, percent: float):
        self.left_water_label.setText(f"水量: {percent:.1f} %")
        self.report_controller.update_left_water(percent)

    def on_right_water_updated(self, percent: float):
        self.right_water_label.setText(f"水量: {percent:.1f} %")
        self.report_controller.update_right_water(percent)

    def on_spray_command_started(self, cmd: str):
        btn = {
            "TARE_LEFT": self.btn_left_tare,
            "SET_LEFT_FULL": self.btn_left_full,
            "TARE_RIGHT": self.btn_right_tare,
            "SET_RIGHT_FULL": self.btn_right_full,
            "LEFT_ON": self.btn_spray_left_on,
            "LEFT_OFF": self.btn_spray_left_off,
            "RIGHT_ON": self.btn_spray_right_on,
            "RIGHT_OFF": self.btn_spray_right_off,
        }.get(cmd)
        if btn:
            btn.setEnabled(False)
            btn.setProperty("old_text", btn.text())
            btn.setText("处理中...")

    def on_spray_command_finished(self, cmd: str, ok: bool):
        btn = {
            "TARE_LEFT": self.btn_left_tare,
            "SET_LEFT_FULL": self.btn_left_full,
            "TARE_RIGHT": self.btn_right_tare,
            "SET_RIGHT_FULL": self.btn_right_full,
            "LEFT_ON": self.btn_spray_left_on,
            "LEFT_OFF": self.btn_spray_left_off,
            "RIGHT_ON": self.btn_spray_right_on,
            "RIGHT_OFF": self.btn_spray_right_off,
        }.get(cmd)
        if btn:
            old_text = btn.property("old_text")
            if old_text:
                btn.setText(old_text)
            btn.setEnabled(True)

    def closeEvent(self, event):
        try:
            self.spray_controller.close()
        except Exception:
            pass
        try:
            self.tcp_client.disconnect()
        except Exception:
            pass
        super().closeEvent(event)

    # ==================== 指挥中心上报 ====================
    def on_report_connect(self):
        if self.report_controller.enabled:
            self.report_controller.stop()
            self.btn_report_connect.setText("连接")
            self.label_report_status.setText("未连接")
            self.label_report_status.setStyleSheet("color: orange; font-weight: bold;")
        else:
            url = self.edit_server_url.text().strip()
            device = self.edit_device_id.text().strip() or "robot_001"
            if not url:
                self.status_bar.showMessage("请输入服务器URL")
                return
            self.report_controller.configure(url, device)
            self.report_controller.start()
            self.btn_report_connect.setText("断开")
            self.label_report_status.setText("已连接")
            self.label_report_status.setStyleSheet("color: green; font-weight: bold;")
            self.status_bar.showMessage("已连接指挥中心，开始上报")

    def on_report_test(self):
        url = self.edit_server_url.text().strip()
        device = self.edit_device_id.text().strip() or "robot_001"
        if not url:
            self.status_bar.showMessage("请输入服务器URL")
            return
        self.report_controller.configure(url, device)
        self.report_controller.test_connection()

    def on_report_status(self, msg: str):
        self.status_bar.showMessage(f"指挥中心: {msg}")

    def on_report_connected(self):
        self.status_bar.showMessage("指挥中心连接测试成功")
        self.label_report_status.setText("测试成功")
        self.label_report_status.setStyleSheet("color: green; font-weight: bold;")

    def on_report_failed(self, err: str):
        self.status_bar.showMessage(f"指挥中心连接失败: {err}")
        self.label_report_status.setText("连接失败")
        self.label_report_status.setStyleSheet("color: red; font-weight: bold;")