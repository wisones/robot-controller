# src/main_window.py
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QGroupBox, QLabel, QStatusBar, QSplitter,
    QLineEdit, QFormLayout
)
from PyQt5.QtCore import Qt
from map_widget import MapWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("智科云机器人控制终端")
        self.setMinimumSize(1000, 700)

        # 创建中心部件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # 左侧/中间：地图显示区域
        self.map_widget = MapWidget()
        self.map_widget.map_clicked.connect(self.on_map_clicked)

        # 右侧：控制面板
        right_panel = self.create_right_panel()

        # 使用 QSplitter 允许调整左右比例
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.map_widget)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)  # 地图占 3/4
        splitter.setStretchFactor(1, 1)  # 面板占 1/4

        main_layout.addWidget(splitter)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 | 未连接机器人")

        # 初始化信号槽（占位）
        self.init_placeholder_connections()

    def create_right_panel(self) -> QWidget:
        """创建右侧控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(15)

        # ---- 底盘连接模块（新增） ----
        conn_group = QGroupBox("底盘连接")
        conn_layout = QFormLayout(conn_group)

        # IP 地址输入框
        self.edit_ip = QLineEdit()
        self.edit_ip.setPlaceholderText("例如: 192.168.1.120")
        conn_layout.addRow("IP 地址:", self.edit_ip)

        # 端口输入框
        self.edit_port = QLineEdit()
        self.edit_port.setPlaceholderText("例如: 9090")
        conn_layout.addRow("端口:", self.edit_port)

        # 连接和 Ping 按钮水平排列
        btn_layout = QHBoxLayout()
        self.btn_connect = QPushButton("连接")
        self.btn_connect.setMinimumHeight(30)
        self.btn_ping = QPushButton("Ping 测试")
        self.btn_ping.setMinimumHeight(30)
        btn_layout.addWidget(self.btn_connect)
        btn_layout.addWidget(self.btn_ping)
        conn_layout.addRow(btn_layout)

        # ---- 地图控制区 ----
        map_group = QGroupBox("地图控制")
        map_layout = QVBoxLayout(map_group)

        self.btn_get_map = QPushButton("获取当前地图")
        self.btn_get_map.setMinimumHeight(35)

        self.btn_show_pose = QPushButton("显示当前位置")
        self.btn_show_pose.setMinimumHeight(35)

        self.btn_set_navi = QPushButton("设定导航")
        self.btn_set_navi.setMinimumHeight(35)
        self.btn_set_navi.setCheckable(True)

        map_layout.addWidget(self.btn_get_map)
        map_layout.addWidget(self.btn_show_pose)
        map_layout.addWidget(self.btn_set_navi)
        map_group.setLayout(map_layout)

        # ---- 喷雾控制区（左侧） ----
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

        # ---- 喷雾控制区（右侧） ----
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

        # ---- 连接状态显示 ----
        status_group = QGroupBox("连接状态")
        status_layout = QVBoxLayout(status_group)
        self.label_conn_status = QLabel("未连接")
        self.label_conn_status.setStyleSheet("color: orange; font-weight: bold;")
        status_layout.addWidget(self.label_conn_status)

        # 将各个组件按顺序加入面板
        layout.addWidget(conn_group)          # 新增的连接模块
        layout.addWidget(map_group)
        layout.addWidget(spray_left_group)
        layout.addWidget(spray_right_group)
        layout.addWidget(status_group)
        layout.addStretch()

        return panel

    def init_placeholder_connections(self):
        """初始化所有按钮的占位槽函数"""
        # 连接模块
        self.btn_connect.clicked.connect(self.on_connect)
        self.btn_ping.clicked.connect(self.on_ping)

        # 地图控制按钮
        self.btn_get_map.clicked.connect(self.on_get_map)
        self.btn_show_pose.clicked.connect(self.on_show_pose)
        self.btn_set_navi.toggled.connect(self.on_set_navi_toggled)

        # 喷雾控制按钮
        self.btn_spray_left_on.clicked.connect(self.on_spray_left_on)
        self.btn_spray_left_off.clicked.connect(self.on_spray_left_off)
        self.btn_spray_right_on.clicked.connect(self.on_spray_right_on)
        self.btn_spray_right_off.clicked.connect(self.on_spray_right_off)

    # ============= 占位槽函数（明天替换为真实逻辑） =============
    def on_connect(self):
        """连接按钮（占位）"""
        ip = self.edit_ip.text().strip()
        port = self.edit_port.text().strip()
        print(f"[占位] 连接到底盘: {ip}:{port}")
        self.status_bar.showMessage(f"尝试连接 {ip}:{port}（功能待实现）")
        # 临时更新状态显示
        self.label_conn_status.setText("连接中...")
        self.label_conn_status.setStyleSheet("color: orange; font-weight: bold;")

    def on_ping(self):
        """Ping测试按钮（占位）"""
        ip = self.edit_ip.text().strip()
        print(f"[占位] Ping 测试: {ip}")
        self.status_bar.showMessage(f"Ping 测试 {ip}（功能待实现）")
        # 这里明天可以用系统 ping 命令或 TCP 连接测试

    def on_get_map(self):
        """获取当前地图（占位）"""
        self.status_bar.showMessage("正在获取地图...（功能待实现）")
        print("[占位] 获取当前地图")
        self.map_widget.setText("地图获取功能\n待明天实现")

    def on_show_pose(self):
        """显示当前位置（占位）"""
        self.status_bar.showMessage("正在获取位置...（功能待实现）")
        print("[占位] 显示当前位置")

    def on_set_navi_toggled(self, checked: bool):
        """设定导航模式切换（占位）"""
        if checked:
            self.status_bar.showMessage("导航设定模式：请在地图上点击目标点（功能待实现）")
            print("[占位] 进入导航设定模式")
        else:
            self.status_bar.showMessage("已退出导航设定模式")
            print("[占位] 退出导航设定模式")

    def on_map_clicked(self, x: int, y: int):
        """地图点击事件（占位）"""
        if self.btn_set_navi.isChecked():
            print(f"[占位] 地图点击坐标: ({x}, {y})，将设定为目标点")
            self.status_bar.showMessage(f"目标点已设定: 像素坐标 ({x}, {y})（功能待实现）")
        else:
            print(f"[占位] 地图点击坐标: ({x}, {y})")

    def on_spray_left_on(self):
        print("[占位] 左侧喷雾 开启")
        self.status_bar.showMessage("左侧喷雾 开启（功能待实现）")

    def on_spray_left_off(self):
        print("[占位] 左侧喷雾 关闭")
        self.status_bar.showMessage("左侧喷雾 关闭（功能待实现）")

    def on_spray_right_on(self):
        print("[占位] 右侧喷雾 开启")
        self.status_bar.showMessage("右侧喷雾 开启（功能待实现）")

    def on_spray_right_off(self):
        print("[占位] 右侧喷雾 关闭")
        self.status_bar.showMessage("右侧喷雾 关闭（功能待实现）")