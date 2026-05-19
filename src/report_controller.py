# src/report_controller.py
import requests
import json
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

class ReportController(QObject):
    status_changed = pyqtSignal(str)        # 上报状态信息（成功/失败）
    connection_ok = pyqtSignal()            # 与指挥中心连接测试成功
    connection_failed = pyqtSignal(str)     # 与指挥中心连接失败

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server_url = ""                # 例如 "http://192.168.1.100:5000/api/robot/status"
        self.device_id = "robot_001"
        self.report_interval = 5            # 上报间隔（秒）
        self.enabled = False

        self._battery = None
        self._left_water = None
        self._right_water = None
        self._tcp_connected = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._send_report)

    def configure(self, server_url: str, device_id: str = "robot_001", interval: int = 5):
        """配置上报参数"""
        self.server_url = server_url.rstrip('/')
        self.device_id = device_id
        self.report_interval = max(1, interval)

    def set_tcp_connected(self, connected: bool):
        self._tcp_connected = connected

    def update_battery(self, percent):
        self._battery = percent

    def update_left_water(self, percent):
        self._left_water = percent

    def update_right_water(self, percent):
        self._right_water = percent

    def start(self):
        """开始定时上报"""
        if not self.server_url:
            self.status_changed.emit("未配置服务器地址")
            return
        self.enabled = True
        self.timer.start(self.report_interval * 1000)
        self.status_changed.emit("上报已启动")

    def stop(self):
        """停止上报"""
        self.enabled = False
        self.timer.stop()
        self.status_changed.emit("上报已停止")

    def test_connection(self):
        """手动测试连接（GET 或 POST 空数据）"""
        if not self.server_url:
            self.connection_failed.emit("未配置服务器地址")
            return
        try:
            r = requests.get(self.server_url, timeout=3)
            if r.status_code == 200:
                self.connection_ok.emit()
            else:
                self.connection_failed.emit(f"HTTP {r.status_code}")
        except Exception as e:
            self.connection_failed.emit(str(e))

    def _send_report(self):
        if not self.enabled or not self.server_url:
            return
        payload = {
            "device_id": self.device_id,
            "tcp_connected": self._tcp_connected,
            "battery": self._battery if self._battery is not None else -1,
            "left_water": self._left_water if self._left_water is not None else -1,
            "right_water": self._right_water if self._right_water is not None else -1,
            "status": "normal" if self._tcp_connected else "disconnected"
        }
        try:
            resp = requests.post(
                self.server_url,
                json=payload,
                timeout=3
            )
            if resp.status_code == 200:
                self.status_changed.emit(f"上报成功 ({self.device_id})")
            else:
                self.status_changed.emit(f"上报失败 HTTP {resp.status_code}")
        except Exception as e:
            self.status_changed.emit(f"上报异常: {e}")