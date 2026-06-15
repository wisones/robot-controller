# src/main_window.py
import math
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QGroupBox, QLabel, QStatusBar, QSplitter,
    QLineEdit, QFormLayout, QSlider, QSpinBox, QComboBox, QCheckBox,
    QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
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

        # PWM控制
        pwm_group = QGroupBox("电机PWM控制")
        pwm_layout = QVBoxLayout(pwm_group)

        # 占空比控制
        duty_layout = QHBoxLayout()
        duty_layout.addWidget(QLabel("占空比:"))
        self.slider_duty = QSlider(Qt.Horizontal)
        self.slider_duty.setRange(0, 100)
        self.slider_duty.setValue(80)
        self.slider_duty.setTickPosition(QSlider.TicksBelow)
        self.slider_duty.setTickInterval(10)
        duty_layout.addWidget(self.slider_duty)
        self.label_duty_value = QLabel("80%")
        self.label_duty_value.setMinimumWidth(40)
        duty_layout.addWidget(self.label_duty_value)
        self.btn_set_duty = QPushButton("设置")
        self.btn_set_duty.setMinimumHeight(30)
        duty_layout.addWidget(self.btn_set_duty)
        pwm_layout.addLayout(duty_layout)

        # 频率控制
        freq_layout = QHBoxLayout()
        freq_layout.addWidget(QLabel("频率(Hz):"))
        self.spin_freq = QSpinBox()
        self.spin_freq.setRange(100, 50000)
        self.spin_freq.setValue(10000)
        self.spin_freq.setSingleStep(1000)
        freq_layout.addWidget(self.spin_freq)
        self.btn_set_freq = QPushButton("设置")
        self.btn_set_freq.setMinimumHeight(30)
        freq_layout.addWidget(self.btn_set_freq)
        pwm_layout.addLayout(freq_layout)

        # 电压提升
        boost_layout = QHBoxLayout()
        boost_layout.addWidget(QLabel("电压提升:"))
        self.slider_boost = QSlider(Qt.Horizontal)
        self.slider_boost.setRange(0, 50)
        self.slider_boost.setValue(0)
        self.slider_boost.setTickPosition(QSlider.TicksBelow)
        self.slider_boost.setTickInterval(5)
        boost_layout.addWidget(self.slider_boost)
        self.label_boost_value = QLabel("0%")
        self.label_boost_value.setMinimumWidth(40)
        boost_layout.addWidget(self.label_boost_value)
        self.btn_set_boost = QPushButton("设置")
        self.btn_set_boost.setMinimumHeight(30)
        boost_layout.addWidget(self.btn_set_boost)
        pwm_layout.addLayout(boost_layout)

        # 模式控制
        mode_layout = QHBoxLayout()
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["连续模式", "脉冲模式"])
        mode_layout.addWidget(self.combo_mode)
        self.btn_set_mode = QPushButton("应用模式")
        self.btn_set_mode.setMinimumHeight(30)
        mode_layout.addWidget(self.btn_set_mode)
        pwm_layout.addLayout(mode_layout)

        # 过驱动控制
        overdrive_layout = QHBoxLayout()
        self.btn_overdrive = QPushButton("过驱动启动")
        self.btn_overdrive.setMinimumHeight(35)
        self.btn_overdrive.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        overdrive_layout.addWidget(self.btn_overdrive)
        self.btn_motor_enable = QPushButton("电机使能")
        self.btn_motor_enable.setMinimumHeight(35)
        self.btn_motor_enable.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold;")
        overdrive_layout.addWidget(self.btn_motor_enable)
        pwm_layout.addLayout(overdrive_layout)

        # PWM配置查询
        config_layout = QHBoxLayout()
        self.btn_get_pwm_config = QPushButton("查询PWM配置")
        self.btn_get_pwm_config.setMinimumHeight(30)
        config_layout.addWidget(self.btn_get_pwm_config)
        self.label_pwm_config = QLabel("未查询")
        config_layout.addWidget(self.label_pwm_config)
        pwm_layout.addLayout(config_layout)

        # 电压优化控制
        optimize_layout = QHBoxLayout()
        self.btn_auto_optimize = QPushButton("自动优化电压")
        self.btn_auto_optimize.setMinimumHeight(35)
        self.btn_auto_optimize.setStyleSheet("background-color: #607D8B; color: white; font-weight: bold;")
        optimize_layout.addWidget(self.btn_auto_optimize)
        pwm_layout.addLayout(optimize_layout)

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
        layout.addWidget(pwm_group)
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

        # PWM控制连接
        self.slider_duty.valueChanged.connect(self.on_duty_slider_changed)
        self.btn_set_duty.clicked.connect(self.on_set_duty)
        self.btn_set_freq.clicked.connect(self.on_set_freq)
        self.slider_boost.valueChanged.connect(self.on_boost_slider_changed)
        self.btn_set_boost.clicked.connect(self.on_set_boost)
        self.btn_set_mode.clicked.connect(self.on_set_mode)
        self.btn_overdrive.clicked.connect(self.on_overdrive)
        self.btn_motor_enable.clicked.connect(self.on_motor_enable)
        self.btn_get_pwm_config.clicked.connect(self.on_get_pwm_config)
        self.btn_auto_optimize.clicked.connect(self.on_auto_optimize)

    def init_tcp_signals(self):
        self.tcp_client.connected.connect(self.on_tcp_connected)
        self.tcp_client.disconnected.connect(self.on_tcp_disconnected)
        self.tcp_client.error_occurred.connect(self.on_tcp_error)
        self.tcp_client.response_received.connect(self.on_response_received)
        self.tcp_client.scan_received.connect(self.on_scan_received)
        self.tcp_client.pose_received.connect(self.on_pose_received)
        self.tcp_client.navi_received.connect(self.on_navi_received)

        # 喷雾控制器信号
        self.spray_controller.pwm_config_received.connect(self.on_pwm_config_received)

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

    # ───────────── PWM控制 ─────────────
    def on_duty_slider_changed(self, value):
        self.label_duty_value.setText(f"{value}%")

    def on_set_duty(self):
        duty = self.slider_duty.value()
        if self.spray_controller.set_pwm_duty(duty):
            self.status_bar.showMessage(f"已设置占空比: {duty}%")
        else:
            self.status_bar.showMessage("占空比设置失败")

    def on_set_freq(self):
        freq = self.spin_freq.value()
        if self.spray_controller.set_pwm_frequency(freq):
            self.status_bar.showMessage(f"已设置PWM频率: {freq}Hz")
        else:
            self.status_bar.showMessage("频率设置失败")

    def on_boost_slider_changed(self, value):
        self.label_boost_value.setText(f"{value}%")

    def on_set_boost(self):
        boost = self.slider_boost.value()
        if self.spray_controller.set_voltage_boost(boost):
            self.status_bar.showMessage(f"已设置电压提升: {boost}%")
        else:
            self.status_bar.showMessage("电压提升设置失败")

    def on_set_mode(self):
        mode = self.combo_mode.currentText()
        if mode == "连续模式":
            self.spray_controller.enable_continuous_mode()
            self.status_bar.showMessage("已切换到连续喷雾模式")
        else:
            self.spray_controller.enable_pulse_mode()
            self.status_bar.showMessage("已切换到脉冲喷雾模式")

    def on_overdrive(self):
        self.spray_controller.overdrive_start(duration_ms=100, duty_percent=100)
        self.status_bar.showMessage("过驱动启动中...")

    def on_motor_enable(self):
        self.spray_controller.set_motor_enable(True)
        self.status_bar.showMessage("电机已使能")

    def on_get_pwm_config(self):
        self.spray_controller.get_pwm_config()
        self.status_bar.showMessage("正在查询PWM配置...")

    def on_pwm_config_received(self, config):
        """接收PWM配置响应"""
        if config:
            # 更新UI显示配置
            duty = config.get('duty', '未知')
            freq = config.get('freq', '未知')
            boost = config.get('boost', '未知')
            mode = config.get('mode', '未知')

            config_text = f"占空比:{duty}%, 频率:{freq}Hz, 提升:{boost}%, 模式:{mode}"
            self.label_pwm_config.setText(config_text)
            self.status_bar.showMessage(f"PWM配置: {config_text}")
        else:
            self.label_pwm_config.setText("解析失败")
            self.status_bar.showMessage("PWM配置解析失败")

    def on_auto_optimize(self):
        """自动优化电压：测试不同参数找到最佳组合"""
        self.status_bar.showMessage("开始自动电压优化...")
        # 这里可以实现自动优化算法
        # 例如：测试不同占空比和频率的组合，监测电压变化
        self._run_voltage_optimization()

    def _run_voltage_optimization(self):
        """运行电压优化算法"""
        # 实现优化逻辑
        # 1. 测试不同占空比 (50%, 60%, 70%, 80%, 90%, 100%)
        # 2. 测试不同频率 (1kHz, 5kHz, 10kHz, 20kHz)
        # 3. 监测电压变化，找到最佳组合

        # 优化参数
        duty_values = [50, 60, 70, 80, 90, 100]
        freq_values = [1000, 5000, 10000, 20000]

        # 存储结果
        self.optimization_results = []
        self.current_optimization_step = 0
        self.total_steps = len(duty_values) * len(freq_values)

        # 开始优化
        self.status_bar.showMessage(f"开始电压优化测试 ({self.total_steps} 步)")

        # 创建定时器逐步测试
        self.optimization_timer = QTimer(self)
        self.optimization_timer.timeout.connect(self._optimization_step)
        self.optimization_timer.start(500)  # 每500ms测试一步

        # 保存当前设置
        self._original_duty = self.slider_duty.value()
        self._original_freq = self.spin_freq.value()

        # 生成测试序列
        self.test_sequence = []
        for duty in duty_values:
            for freq in freq_values:
                self.test_sequence.append((duty, freq))

    def _optimization_step(self):
        """优化步骤：测试下一组参数"""
        if self.current_optimization_step >= self.total_steps:
            # 优化完成
            self.optimization_timer.stop()
            self._finish_optimization()
            return

        # 获取当前测试参数
        duty, freq = self.test_sequence[self.current_optimization_step]

        # 设置参数
        self.spray_controller.set_pwm_duty(duty)
        self.spray_controller.set_pwm_frequency(freq)

        # 更新UI
        self.slider_duty.setValue(duty)
        self.spin_freq.setValue(freq)

        # 记录当前电压
        current_voltage = float(self.voltage_label.text().split(":")[1].split("V")[0].strip())

        # 存储结果
        self.optimization_results.append({
            'duty': duty,
            'freq': freq,
            'voltage': current_voltage,
            'step': self.current_optimization_step
        })

        # 更新状态
        self.status_bar.showMessage(
            f"优化测试 {self.current_optimization_step+1}/{self.total_steps}: "
            f"占空比{duty}%, 频率{freq}Hz, 电压{current_voltage:.1f}V"
        )

        self.current_optimization_step += 1

    def _finish_optimization(self):
        """完成优化，分析结果"""
        if not self.optimization_results:
            self.status_bar.showMessage("优化测试无结果")
            return

        # 找到最佳参数（电压最高的组合）
        best_result = max(self.optimization_results, key=lambda x: x['voltage'])

        # 恢复原始设置
        self.spray_controller.set_pwm_duty(self._original_duty)
        self.spray_controller.set_pwm_frequency(self._original_freq)
        self.slider_duty.setValue(self._original_duty)
        self.spin_freq.setValue(self._original_freq)

        # 显示结果
        self.status_bar.showMessage(
            f"优化完成！最佳参数: 占空比{best_result['duty']}%, "
            f"频率{best_result['freq']}Hz, 电压{best_result['voltage']:.1f}V"
        )

        # 询问是否应用最佳参数
        reply = QMessageBox.question(
            self, "优化结果",
            f"找到最佳参数组合:\n"
            f"占空比: {best_result['duty']}%\n"
            f"频率: {best_result['freq']}Hz\n"
            f"电压: {best_result['voltage']:.1f}V\n\n"
            f"是否应用这些参数？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.spray_controller.set_pwm_duty(best_result['duty'])
            self.spray_controller.set_pwm_frequency(best_result['freq'])
            self.slider_duty.setValue(best_result['duty'])
            self.spin_freq.setValue(best_result['freq'])
            self.status_bar.showMessage("已应用最佳参数")