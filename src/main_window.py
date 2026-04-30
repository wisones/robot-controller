# src/main_window.py
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QGroupBox, QLabel, QStatusBar, QSplitter,
    QLineEdit, QFormLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from map_widget import MapWidget
from tcp_client import RobotTCPClient
import base64
import struct

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("智科云机器人控制终端")
        self.setMinimumSize(1000, 700)

        self.map_meta = None
        self.current_map_name = ""

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

        self.edit_ip.setText("192.168.10.159")
        self.edit_port.setText("10000")

    # ---------- UI 构建 ----------
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

        self.btn_set_navi = QPushButton("设定导航")
        self.btn_set_navi.setMinimumHeight(35)
        self.btn_set_navi.setCheckable(True)

        map_layout.addWidget(self.btn_get_map)
        map_layout.addWidget(self.btn_sub_scan)
        map_layout.addWidget(self.btn_show_pose)
        map_layout.addWidget(self.btn_set_navi)
        map_group.setLayout(map_layout)

        # 左侧喷雾
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

        # 右侧喷雾
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
        status_layout.addWidget(self.label_conn_status)

        layout.addWidget(conn_group)
        layout.addWidget(map_group)
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
        self.btn_set_navi.toggled.connect(self.on_set_navi_toggled)
        self.btn_spray_left_on.clicked.connect(self.on_spray_left_on)
        self.btn_spray_left_off.clicked.connect(self.on_spray_left_off)
        self.btn_spray_right_on.clicked.connect(self.on_spray_right_on)
        self.btn_spray_right_off.clicked.connect(self.on_spray_right_off)

    def init_tcp_signals(self):
        self.tcp_client.connected.connect(self.on_tcp_connected)
        self.tcp_client.disconnected.connect(self.on_tcp_disconnected)
        self.tcp_client.error_occurred.connect(self.on_tcp_error)
        self.tcp_client.response_received.connect(self.on_response_received)
        self.tcp_client.scan_received.connect(self.on_scan_received)   # 雷达点云
        self.tcp_client.pose_received.connect(self.on_pose_received)   # 可预留

    # ---------- TCP 状态回调 ----------
    def on_tcp_connected(self):
        self.label_conn_status.setText("已连接")
        self.label_conn_status.setStyleSheet("color: green; font-weight: bold;")
        self.status_bar.showMessage("底盘连接成功，自动订阅位置...")
        # 自动订阅位置
        self.tcp_client.send_command({"CMD": "CMD_SUB_POSE"})

    def on_tcp_disconnected(self):
        self.label_conn_status.setText("未连接")
        self.label_conn_status.setStyleSheet("color: orange; font-weight: bold;")
        self.status_bar.showMessage("底盘连接已断开")

    def on_tcp_error(self, err_msg: str):
        print(f"[TCP 错误] {err_msg}")
        self.status_bar.showMessage(f"错误: {err_msg}")

    # ---------- 通用响应处理 ----------
    def on_response_received(self, data: dict):
        cmd = data.get("CMD", "")
        if cmd == "CMD_GET_VERSION":
            version = data.get("VERSION", "未知")
            self.status_bar.showMessage(f"Ping 成功！版本: {version}")
        elif cmd == "CMD_GET_CURRENT_MAP_CONFIG":
            map_config = data.get("MAP_CURRENT_CONFIG", {})
            map_name = map_config.get("STATIC_MAP_NAME", "")
            if map_name:
                self.current_map_name = map_name
                self.status_bar.showMessage(f"当前地图: {map_name}，正在获取元数据...")
                self.tcp_client.send_command({
                    "CMD": "CMD_GET_MAP_META_DATA",
                    "MAP_NAME": map_name
                })
            else:
                self.status_bar.showMessage("获取地图名称失败，可能没有已保存的地图")
        elif cmd == "CMD_GET_MAP_META_DATA":
            meta = data.get("MAP_META_DATA", {})
            self.map_meta = meta
            self.map_widget.set_map_meta(meta)   # 传递元数据
            self.status_bar.showMessage("元数据已获取，正在下载静态地图...")
            if self.current_map_name:
                self.tcp_client.send_command({
                    "CMD": "CMD_GET_MAP_DATA",
                    "MAP_NAME": self.current_map_name
                })
            else:
                self.status_bar.showMessage("地图名称丢失，请重新获取")
        elif cmd == "CMD_GET_MAP_DATA":
            map_data_b64 = data.get("MAP_DATA", "")
            if map_data_b64:
                self.display_map(map_data_b64)
                self.status_bar.showMessage("静态地图加载成功")
            else:
                self.status_bar.showMessage("地图数据为空")

    # ---------- 地图 ----------
    def on_get_map(self):
        if not self.tcp_client.is_connected:
            self.status_bar.showMessage("请先连接底盘")
            return
        self.status_bar.showMessage("正在获取地图配置...")
        self.tcp_client.send_command({"CMD": "CMD_GET_CURRENT_MAP_CONFIG"})

    def display_map(self, b64_data: str):
        try:
            img_bytes = base64.b64decode(b64_data)
            self.map_widget.set_map_from_bytes(img_bytes)
        except Exception as e:
            self.status_bar.showMessage(f"地图解码失败: {str(e)}")

    # ---------- 激光扫描 ----------
    def on_sub_scan_toggled(self, checked: bool):
        if not self.tcp_client.is_connected:
            self.status_bar.showMessage("请先连接底盘")
            self.btn_sub_scan.setChecked(False)
            return
        if checked:
            self.tcp_client.send_command({"CMD": "CMD_SUB_SCAN"})
            self.status_bar.showMessage("已订阅激光扫描数据，等待推送...")
        else:
            self.tcp_client.send_command({"CMD": "CMD_CANCEL_SUB_SCAN"})
            self.status_bar.showMessage("已取消订阅激光扫描")

    def on_scan_received(self, data: dict):
        b64_data = data.get("LASER_SCAN", "")
        if not b64_data:
            return
        try:
            raw = base64.b64decode(b64_data)
            points = []
            # 每个点 x,y,z 三个 float32（小端）
            for i in range(0, len(raw), 12):
                if i + 12 > len(raw):
                    break
                x, y, z = struct.unpack('<fff', raw[i:i+12])
                points.append((x, y))
            self.map_widget.set_scan_points(points)
        except Exception as e:
            self.status_bar.showMessage(f"点云解析错误: {str(e)}")

    # ---------- 其他按钮（占位） ----------
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
        self.status_bar.showMessage("Ping 测试中，等待回复...")
        self.tcp_client.send_command({"CMD": "CMD_GET_VERSION"})

    def on_show_pose(self):
        self.status_bar.showMessage("位置显示功能暂未实现")

    def on_set_navi_toggled(self, checked: bool):
        if checked:
            self.status_bar.showMessage("导航设定模式：请在地图上点击目标点（待实现）")
        else:
            self.status_bar.showMessage("已退出导航设定模式")

    def on_map_clicked(self, x: int, y: int):
        if self.btn_set_navi.isChecked():
            print(f"地图点击坐标: ({x}, {y})")
            self.status_bar.showMessage(f"目标点已设定: 像素 ({x}, {y})，功能待实现")

    def on_spray_left_on(self):
        print("左侧喷雾 开启")

    def on_spray_left_off(self):
        print("左侧喷雾 关闭")

    def on_spray_right_on(self):
        print("右侧喷雾 开启")

    def on_spray_right_off(self):
        print("右侧喷雾 关闭")

    # 预留位置回调
    def on_pose_received(self, data: dict):
        pose = data.get("ROBOT_POSE", None)
        if pose:
            x = pose.get("X", 0.0)
            y = pose.get("Y", 0.0)
            theta = pose.get("THETA", 0.0)
            self.map_widget.set_robot_pose(x, y, theta)
        pass