# src/spray_controller.py
import socket
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

class SprayController(QObject):
    voltage_updated = pyqtSignal(float)
    connection_error = pyqtSignal(str)

    def __init__(self, esp_ip="192.168.10.200", esp_port=8266, parent=None):
        super().__init__(parent)
        self.esp_ip = esp_ip
        self.esp_port = esp_port
        self.sock = None

        self.volt_timer = QTimer(self)
        self.volt_timer.timeout.connect(self._request_voltage)
        self.volt_timer.start(2000)

        self._connect()

    def _connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(2)
            self.sock.connect((self.esp_ip, self.esp_port))
            print(f"喷雾控制器已连接到 {self.esp_ip}:{self.esp_port}")
        except Exception as e:
            self.connection_error.emit(f"喷雾控制器连接失败: {e}")
            self.sock = None

    def _send_cmd(self, cmd):
        if not self.sock:
            self._connect()
            if not self.sock:
                return
        try:
            self.sock.send((cmd + "\n").encode())
        except Exception as e:
            self.connection_error.emit(f"发送指令失败: {e}")
            self.sock = None

    def left_on(self):
        self._send_cmd("LEFT_ON")
    def left_off(self):
        self._send_cmd("LEFT_OFF")
    def right_on(self):
        self._send_cmd("RIGHT_ON")
    def right_off(self):
        self._send_cmd("RIGHT_OFF")

    def _request_voltage(self):
        if not self.sock:
            return
        try:
            self.sock.send("GET_VOLTAGE\n".encode())
            data = self.sock.recv(64).decode().strip().replace('V', '')
            voltage = float(data)
            self.voltage_updated.emit(voltage)
        except Exception as e:
            self.connection_error.emit(f"电压读取失败: {e}")
            self.sock = None

    def close(self):
        if self.sock:
            self.sock.close()
        self.volt_timer.stop()