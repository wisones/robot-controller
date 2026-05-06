# src/main_window.py
import math
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QGroupBox, QLabel, QStatusBar, QSplitter,
    QLineEdit, QFormLayout
)
from PyQt5.QtCore import Qt
from map_widget import MapWidget
from tcp_client import RobotTCPClient
from spray_controller import SprayController
import base64
import struct

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("智科云机器人控制终端")
        self.setMinimumSize(1000, 700)

        self.map_meta = None
        self.current_map_name = ""

        self.goal_points = []
        self.navi_queue = []
        self.current_navi_index = 0
        self.nav_state = 'idle'
        self.fail_count = 0

        self.robot_x = 0.0
        self.robot_y = 0.0
        self.latest_theta = 0.0

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        self.map_widget = MapWidget()
        self.map_widget.map_clicked.connect(self.on_map_clicked)

        right_panel = self.create_right_panel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.map_widget)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 | 未连接机器人")

        self.tcp_client = RobotTCPClient()
        self.init_tcp_signals()
        self.init_ui_connections()

        # 喷雾控制器
        self.spray_controller = SprayController(esp_ip="192.168.10.200")
        self.spray_controller.connection_error.connect(self.on_spray_error)
        self.spray_controller.voltage_updated.connect(self.on_voltage_updated)

        self.edit_ip.setText("192.168.10.159")
        self.edit_port.setText("10000")

    # ───────────── UI 构建 ─────────────
    def create_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(15)

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

        # 喷雾控制
        spray_left_group = QGroupBox("左侧喷雾")
        spray_left_layout = QHBoxLayout(spray_left_group)
        self.btn_spray_left_on = QPushButton("开启")
        self.btn_spray_left_on.setMinimumHeight(40)
        self.btn_spray_left_on.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_spray_left_off = QPushButton("关闭")
        self.btn_spray_left_off.setMinimumHeight(40)
        self.btn_spray_left_off.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        spray_left_layout.addWidget(self.btn_spray_left_on)
        spray_left_layout.addWidget(self.btn_spray_left_off)

        spray_right_group = QGroupBox("右侧喷雾")
        spray_right_layout = QHBoxLayout(spray_right_group)
        self.btn_spray_right_on = QPushButton("开启")
        self.btn_spray_right_on.setMinimumHeight(40)
        self.btn_spray_right_on.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_spray_right_off = QPushButton("关闭")
        self.btn_spray_right_off.setMinimumHeight(40)
        self.btn_spray_right_off.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        spray_right_layout.addWidget(self.btn_spray_right_on)
        spray_right_layout.addWidget(self.btn_spray_right_off)

        # 连接状态
        status_group = QGroupBox("连接状态")
        status_layout = QVBoxLayout(status_group)
        self.label_conn_status = QLabel("未连接")
        self.label_conn_status.setStyleSheet("color: orange; font-weight: bold;")
        self.voltage_label = QLabel("电池电压: --- V")
        status_layout.addWidget(self.label_conn_status)
        status_layout.addWidget(self.voltage_label)

        layout.addWidget(conn_group)
        layout.addWidget(map_group)
        layout.addWidget(navi_group)
        layout.addWidget(spray_left_group)
        layout.addWidget(spray_right_group)
        layout.addWidget(status_group)
        layout.addStretch()
        return panel

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
        self.btn_spray_left_on.clicked.connect(self.on_spray_left_on)
        self.btn_spray_left_off.clicked.connect(self.on_spray_left_off)
        self.btn_spray_right_on.clicked.connect(self.on_spray_right_on)
        self.btn_spray_right_off.clicked.connect(self.on_spray_right_off)

    def init_tcp_signals(self):
        self.tcp_client.connected.connect(self.on_tcp_connected)
        self.tcp_client.disconnected.connect(self.on_tcp_disconnected)
        self.tcp_client.error_occurred.connect(self.on_tcp_error)
        self.tcp_client.response_received.connect(self.on_response_received)
        self.tcp_client.scan_received.connect(self.on_scan_received)
        self.tcp_client.pose_received.connect(self.on_pose_received)
        self.tcp_client.navi_received.connect(self.on_navi_received)

    # ───────────── TCP 回调 ─────────────
    def on_tcp_connected(self):
        self.label_conn_status.setText("已连接")
        self.label_conn_status.setStyleSheet("color: green; font-weight: bold;")
        self.status_bar.showMessage("底盘连接成功，自动订阅位置...")
        self.tcp_client.send_command({"CMD": "CMD_SUB_POSE"})

    def on_tcp_disconnected(self):
        self.label_conn_status.setText("未连接")
        self.label_conn_status.setStyleSheet("color: orange; font-weight: bold;")
        self.status_bar.showMessage("底盘连接已断开")

    def on_tcp_error(self, err_msg: str):
        print(f"[TCP 错误] {err_msg}")
        self.status_bar.showMessage(f"错误: {err_msg}")

    def on_response_received(self, data: dict):
        cmd = data.get("CMD", "")
        if cmd == "CMD_GET_VERSION":
            version = data.get("VERSION", "未知")
            self.status_bar.showMessage(f"版本: {version}")
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
            meta = data.get("MAP_META_DATA", {})
            self.map_meta = meta
            self.map_widget.set_map_meta(meta)
            self.status_bar.showMessage("元数据已获取，正在下载地图...")
            if self.current_map_name:
                self.tcp_client.send_command({"CMD": "CMD_GET_MAP_DATA", "MAP_NAME": self.current_map_name})
        elif cmd == "CMD_GET_MAP_DATA":
            map_data_b64 = data.get("MAP_DATA", "")
            if map_data_b64:
                self.display_map(map_data_b64)
                self.status_bar.showMessage("地图加载成功")

    # ───────────── 地图 / 点云 / 位置 ─────────────
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
            self.robot_x = pose.get("X", 0.0)
            self.robot_y = pose.get("Y", 0.0)
            self.latest_theta = pose.get("THETA", 0.0)
            self.map_widget.set_robot_pose(self.robot_x, self.robot_y, self.latest_theta)

    def on_show_pose(self):
        self.status_bar.showMessage("位置实时显示中")

    # ───────────── 导航 ─────────────
    def on_add_goal_toggled(self, checked: bool):
        if checked:
            self.status_bar.showMessage("在地图上点击添加目标点")
        else:
            self.status_bar.showMessage("已退出添加模式")

    def on_map_clicked(self, x: int, y: int):
        if not self.btn_add_goal.isChecked():
            return
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
        cmd = {
            "CMD": "CMD_NAV_BY_POSE2D",
            "X": wx,
            "Y": wy,
            "THETA": theta
        }
        self.tcp_client.send_command(cmd)
        self.status_bar.showMessage(
            f"前往目标点 {self.current_navi_index+1}/{len(self.navi_queue)}")

    def _finish_navigation(self):
        self.nav_state = 'idle'
        self.navi_queue.clear()
        self.current_navi_index = 0
        self.fail_count = 0
        self.status_bar.showMessage("顺序导航完成")

    def on_navi_received(self, data: dict):
        if self.nav_state != 'navigating':
            return
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

    # ───────────── 连接 / Ping ─────────────
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

    # ───────────── 喷雾 ─────────────
    def on_spray_left_on(self):   self.spray_controller.left_on()
    def on_spray_left_off(self):  self.spray_controller.left_off()
    def on_spray_right_on(self):  self.spray_controller.right_on()
    def on_spray_right_off(self): self.spray_controller.right_off()
    def on_spray_error(self, msg: str):
        self.status_bar.showMessage(f"喷雾错误: {msg}")
    def on_voltage_updated(self, volt: float):
        self.voltage_label.setText(f"电池电压: {volt:.1f} V")