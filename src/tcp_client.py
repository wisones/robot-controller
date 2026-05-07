# src/tcp_client.py
import socket
import json
import struct
import time
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

class RobotTCPClient(QObject):
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    error_occurred = pyqtSignal(str)
    pose_received = pyqtSignal(dict)
    map_received = pyqtSignal(dict)
    navi_received = pyqtSignal(dict)
    goal_received = pyqtSignal(dict)
    global_path_received = pyqtSignal(dict)
    local_path_received = pyqtSignal(dict)
    scan_received = pyqtSignal(dict)
    camera_pointcloud_received = pyqtSignal(dict)
    response_received = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sock = None
        self.buffer = b''
        self._connected = False
        self._ip = None
        self._port = None

        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.timeout.connect(self.send_heartbeat)
        self.heartbeat_timer.setInterval(3000)

        self._recv_timer = QTimer(self)
        self._recv_timer.timeout.connect(self._try_recv)
        self._recv_timer.setInterval(50)

    def connect_to_robot(self, ip: str, port: int):
        if self._connected:
            return
        self._ip = ip
        self._port = port
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(3.0)
            self.sock.connect((ip, port))
            self.sock.setblocking(False)
            self._connected = True
            self.connected.emit()
            self.heartbeat_timer.start()
            self._recv_timer.start()
        except Exception as e:
            self.error_occurred.emit(f"连接失败: {str(e)}")
            self._connected = False

    def disconnect(self):
        self.heartbeat_timer.stop()
        self._recv_timer.stop()
        self._connected = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
        self.disconnected.emit()

    def send_command(self, cmd_data: dict, auto_queue=True):
        if not self._connected or not self.sock:
            self.error_occurred.emit("未连接到底盘，无法发送命令")
            return False
        if auto_queue:
            if "MSG_TYPE" not in cmd_data:
                cmd_data["MSG_TYPE"] = "CLIENT_REQUEST"
            if "QUEUE_NUMBER" not in cmd_data:
                cmd_data["QUEUE_NUMBER"] = int(time.time() * 1000) % 1000000
        try:
            json_str = json.dumps(cmd_data)
            data_bytes = json_str.encode('utf-8')
            length_bytes = len(data_bytes).to_bytes(4, 'little')
            packet = b'\x88' + length_bytes + data_bytes + b'\xAA'
            self.sock.send(packet)
            return True
        except Exception as e:
            self.error_occurred.emit(f"发送失败: {str(e)}")
            return False

    def send_heartbeat(self):
        if self._connected:
            self.send_command({"CMD": "HEART_BEAT"}, auto_queue=False)

    def _try_recv(self):
        if not self._connected or not self.sock:
            return
        try:
            data = self.sock.recv(4096)
            if data:
                self.buffer += data
                self._parse_buffer()
        except BlockingIOError:
            pass
        except ConnectionError as e:
            self.error_occurred.emit(f"连接断开: {str(e)}")
            self.disconnect()
        except Exception as e:
            self.error_occurred.emit(f"接收异常: {str(e)}")

    def _parse_buffer(self):
        while True:
            if len(self.buffer) < 5:
                break
            if self.buffer[0] != 0x88:
                idx = self.buffer.find(b'\x88', 1)
                if idx == -1:
                    self.buffer = b''
                else:
                    self.buffer = self.buffer[idx:]
                continue
            length = int.from_bytes(self.buffer[1:5], 'little')
            total_len = 5 + length + 1
            if len(self.buffer) < total_len:
                break
            if self.buffer[5 + length] != 0xAA:
                self.buffer = self.buffer[1:]
                continue
            json_bytes = self.buffer[5:5 + length]
            self.buffer = self.buffer[total_len:]
            try:
                msg = json.loads(json_bytes.decode('utf-8'))
                self._handle_message(msg)
            except Exception as e:
                self.error_occurred.emit(f"JSON 解析错误: {str(e)}")

    def _handle_message(self, data: dict):
        msg_type = data.get("MSG_TYPE", "")
        cmd = data.get("CMD", "")
        if msg_type == "SERVER_RESPONSE":
            error_code = data.get("ERROR_CODE", -1)
            if error_code != 0:
                self.error_occurred.emit(f"命令 {cmd} 错误 {error_code}: {data.get('ERROR_MSG', '')}")
            self.response_received.emit(data)
        elif msg_type == "SERVER_REPORT":
            if cmd == "CMD_PUB_POSE":
                self.pose_received.emit(data)
            elif cmd == "CMD_PUB_MAP":
                self.map_received.emit(data)
            elif cmd == "CMD_PUB_NAVI":
                self.navi_received.emit(data)
            elif cmd == "CMD_PUB_GOAL":
                self.goal_received.emit(data)
            elif cmd == "CMD_PUB_GLOBAL_PATH":
                self.global_path_received.emit(data)
            elif cmd == "CMD_PUB_LOCAL_PATH":
                self.local_path_received.emit(data)
            elif cmd == "CMD_PUB_SCAN":
                self.scan_received.emit(data)
            elif cmd == "CMD_PUB_CAMERA_POINTCLOUD":
                self.camera_pointcloud_received.emit(data)

    @property
    def is_connected(self):
        return self._connected