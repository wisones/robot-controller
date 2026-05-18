import socket
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QMutex

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
        self.mutex = QMutex()

        self.water_timer = QTimer(self)
        self.water_timer.timeout.connect(self._request_water)
        self.water_timer.start(2000)

        self._connect()

    def _connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(3)
            self.sock.connect((self.esp_ip, self.esp_port))
            print(f"喷雾控制器已连接到 {self.esp_ip}:{self.esp_port}")
        except Exception as e:
            self.connection_error.emit(f"喷雾控制器连接失败: {e}")
            self.sock = None

    def _send_and_recv(self, cmd: str, timeout=2.0):
        self.mutex.lock()
        try:
            if self.sock is None:
                return None
            # 清空缓冲区
            self.sock.settimeout(0.1)
            try:
                while True:
                    self.sock.recv(1024)
            except:
                pass

            self.sock.settimeout(timeout)
            self.sock.sendall((cmd + "\n").encode())

            data = b""
            while True:
                try:
                    chunk = self.sock.recv(1)
                    if not chunk:
                        break
                    data += chunk
                    if chunk == b'\n':
                        break
                except (socket.timeout, TimeoutError, OSError):
                    break
            resp = data.decode().strip()
            return resp if resp else None
        except Exception as e:
            self.connection_error.emit(f"通信失败: {e}")
            self.sock = None
            return None
        finally:
            self.mutex.unlock()

    # 泵控制
    def left_on(self):    self._send_and_recv("LEFT_ON")
    def left_off(self):   self._send_and_recv("LEFT_OFF")
    def right_on(self):   self._send_and_recv("RIGHT_ON")
    def right_off(self):  self._send_and_recv("RIGHT_OFF")

    # 校准
    def tare_left(self):
        resp = self._send_and_recv("TARE_LEFT")
        self.status_message.emit("左校准完成" if resp == "OK" else "左校准失败")

    def tare_right(self):
        resp = self._send_and_recv("TARE_RIGHT")
        self.status_message.emit("右校准完成" if resp == "OK" else "右校准失败")

    def set_left_full(self):
        resp = self._send_and_recv("SET_LEFT_FULL")
        self.status_message.emit("左设满完成" if resp == "OK" else "左设满失败")

    def set_right_full(self):
        resp = self._send_and_recv("SET_RIGHT_FULL")
        self.status_message.emit("右设满完成" if resp == "OK" else "右设满失败")

    # 水位
    def _request_water(self):
        resp = self._send_and_recv("GET_WATER")
        if resp is None:
            return
        try:
            parts = resp.split(',')
            if len(parts) == 2:
                self.left_water_updated.emit(float(parts[0]))
                self.right_water_updated.emit(float(parts[1]))
        except ValueError:
            self.status_message.emit("水位格式错误")

    def close(self):
        self.water_timer.stop()
        if self.sock:
            self.sock.close()