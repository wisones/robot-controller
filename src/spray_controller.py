# src/spray_controller.py
import socket
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

class SprayController(QObject):
    connection_error = pyqtSignal(str)
    status_message = pyqtSignal(str)
    left_water_updated = pyqtSignal(float)
    right_water_updated = pyqtSignal(float)

    def __init__(self, esp_ip="192.168.10.200", esp_port=8266, parent=None):
        super().__init__(parent)
        self.esp_ip = esp_ip
        self.esp_port = esp_port
        self.sock = None

        self.water_timer = QTimer(self)
        self.water_timer.timeout.connect(self._request_water)
        self.water_timer.start(2000)

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
            self.sock.sendall((cmd + "\n").encode())
        except Exception as e:
            self.connection_error.emit(f"发送指令失败: {e}")
            self.sock = None

    # 水泵
    def left_on(self):       self._send_cmd("LEFT_ON")
    def left_off(self):      self._send_cmd("LEFT_OFF")
    def right_on(self):      self._send_cmd("RIGHT_ON")
    def right_off(self):     self._send_cmd("RIGHT_OFF")

    # 校准
    def tare_left(self):
        self._send_cmd("TARE_LEFT")
        self.status_message.emit("左液面校准完成")
    def tare_right(self):
        self._send_cmd("TARE_RIGHT")
        self.status_message.emit("右液面校准完成")
    def set_left_full(self):
        self._send_cmd("SET_LEFT_FULL")
        self.status_message.emit("左设满完成")
    def set_right_full(self):
        self._send_cmd("SET_RIGHT_FULL")
        self.status_message.emit("右设满完成")

    # 水位查询
    def _request_water(self):
        if not self.sock:
            return
        try:
            self.sock.sendall(b"GET_WATER\n")
            self.sock.settimeout(0.5)
            data = b""
            while True:
                ch = self.sock.recv(1)
                if not ch: break
                data += ch
                if ch == b'\n': break
            line = data.decode().strip()
            if line:
                parts = line.split(',')
                if len(parts) == 2:
                    self.left_water_updated.emit(float(parts[0]))
                    self.right_water_updated.emit(float(parts[1]))
        except:
            pass

    # 软件复位
    def send_reset(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect((self.esp_ip, self.esp_port))
            s.sendall(b"RESET\n")
            s.close()
        except:
            pass

    def close(self):
        self.water_timer.stop()
        if self.sock:
            self.sock.close()