# src/spray_controller.py
import itertools
import queue
import socket
import threading
import time
from PyQt5.QtCore import QObject, pyqtSignal, QTimer


class SprayController(QObject):
    """ESP8266 喷雾/液位控制器。

    关键点：所有 socket、重连、RST、等待响应都放到后台线程执行，
    UI 线程只负责入队命令和接收信号，因此点击“液面校准/设满”不会卡界面。
    """

    connection_error = pyqtSignal(str)
    status_message = pyqtSignal(str)
    left_water_updated = pyqtSignal(float)
    right_water_updated = pyqtSignal(float)
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    # UI 可用这两个信号把按钮置为“处理中...”
    command_started = pyqtSignal(str)
    command_finished = pyqtSignal(str, bool)

    def __init__(
        self,
        esp_ip="192.168.10.200",
        esp_port=8266,
        parent=None,
        water_interval_ms=1000,
        connect_timeout=0.8,
        response_timeout=0.8,
    ):
        super().__init__(parent)
        self.esp_ip = esp_ip
        self.esp_port = esp_port
        self.connect_timeout = connect_timeout
        self.response_timeout = response_timeout

        self.sock = None
        self._stop_event = threading.Event()
        self._cmd_queue = queue.PriorityQueue()
        self._seq = itertools.count()
        self._state_lock = threading.Lock()
        self._water_pending = False
        self._user_cmd_pending = set()
        self._last_connect_attempt = 0.0
        self._last_reset_time = 0.0
        self._connect_fail_count = 0

        self._worker = threading.Thread(target=self._worker_loop, name="SprayControllerWorker", daemon=True)
        self._worker.start()

        self.water_timer = QTimer(self)
        self.water_timer.timeout.connect(self._request_water)
        self.water_timer.start(water_interval_ms)

        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.timeout.connect(self._try_reconnect)
        self._reconnect_timer.start(3000)

        # 初始化连接也异步执行，避免窗口启动时卡 2~5 秒。
        self._enqueue_internal("_CONNECT")

    # ==================== 入队接口：UI 线程立即返回 ====================
    def _enqueue_internal(self, cmd: str):
        self._cmd_queue.put((10, next(self._seq), cmd, "", False, "internal"))

    def _enqueue_command(self, cmd: str, label: str, priority: int = 0, expect_response: bool = True) -> bool:
        with self._state_lock:
            if cmd == "GET_WATER":
                # 上一次液位读取还没处理完时跳过，防止队列堆积拖慢校准/设满。
                if self._water_pending:
                    return False
                self._water_pending = True
                kind = "water"
                priority = 5
            else:
                if cmd in self._user_cmd_pending:
                    return False
                self._user_cmd_pending.add(cmd)
                kind = "user"

        if kind == "user":
            self.command_started.emit(cmd)
            self.status_message.emit(f"{label}中...")

        self._cmd_queue.put((priority, next(self._seq), cmd, label, expect_response, kind))
        return True

    # ---- 泵控制 ----
    def left_on(self):
        self._enqueue_command("LEFT_ON", "左喷雾开启", expect_response=True)

    def left_off(self):
        self._enqueue_command("LEFT_OFF", "左喷雾关闭", expect_response=True)

    def right_on(self):
        self._enqueue_command("RIGHT_ON", "右喷雾开启", expect_response=True)

    def right_off(self):
        self._enqueue_command("RIGHT_OFF", "右喷雾关闭", expect_response=True)

    # ---- 校准 ----
    def tare_left(self):
        self._enqueue_command("TARE_LEFT", "左液面校准", expect_response=True)

    def tare_right(self):
        self._enqueue_command("TARE_RIGHT", "右液面校准", expect_response=True)

    def set_left_full(self):
        self._enqueue_command("SET_LEFT_FULL", "左设满", expect_response=True)

    def set_right_full(self):
        self._enqueue_command("SET_RIGHT_FULL", "右设满", expect_response=True)

    # ---- 水位 ----
    def _request_water(self):
        self._enqueue_command("GET_WATER", "液位读取", priority=5, expect_response=True)

    def _try_reconnect(self):
        if self.sock is None:
            self._enqueue_internal("_CONNECT")

    # ==================== 后台线程 ====================
    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                _priority, _seq, cmd, label, expect_response, kind = self._cmd_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if cmd == "_STOP":
                break

            try:
                if cmd == "_CONNECT":
                    self._ensure_connected(force=False)
                    continue

                ok = False
                resp = None
                if self._ensure_connected(force=False):
                    resp = self._send_and_recv(cmd, timeout=self.response_timeout)
                    ok = (resp == "OK") if cmd != "GET_WATER" else bool(resp)

                if cmd == "GET_WATER":
                    self._handle_water_response(resp)
                else:
                    self._handle_user_response(cmd, label, ok, resp)
            finally:
                with self._state_lock:
                    if kind == "water":
                        self._water_pending = False
                    elif kind == "user":
                        self._user_cmd_pending.discard(cmd)

    def _ensure_connected(self, force: bool = False) -> bool:
        if self.sock is not None and not force:
            return True

        now = time.monotonic()
        if not force and now - self._last_connect_attempt < 1.0:
            return self.sock is not None
        self._last_connect_attempt = now

        self._close_socket(emit_signal=False)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.connect_timeout)
            s.connect((self.esp_ip, self.esp_port))
            self.sock = s
            self._connect_fail_count = 0
            self.connected.emit()
            return True
        except Exception as e:
            self.sock = None
            self._connect_fail_count += 1
            # 连续失败时再复位 ESP，且复位也在后台线程中执行，不阻塞 UI。
            if self._connect_fail_count >= 3 and now - self._last_reset_time > 15:
                self._reset_esp_background()
            self.connection_error.emit(f"喷雾控制器连接失败: {e}")
            return False

    def _reset_esp_background(self):
        self._last_reset_time = time.monotonic()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.6)
            s.connect((self.esp_ip, self.esp_port))
            s.sendall(b"RST\n")
            s.close()
            time.sleep(2.5)  # 只在后台线程等待 ESP 重启
        except Exception:
            pass

    def _clear_buffer(self):
        if not self.sock:
            return
        old_timeout = self.sock.gettimeout()
        try:
            self.sock.setblocking(False)
            while True:
                try:
                    chunk = self.sock.recv(1024)
                    if not chunk:
                        break
                except BlockingIOError:
                    break
        finally:
            try:
                self.sock.setblocking(True)
                self.sock.settimeout(old_timeout)
            except OSError:
                pass

    def _send_and_recv(self, cmd: str, timeout: float = 0.8):
        if self.sock is None:
            return None
        try:
            self._clear_buffer()
            self.sock.settimeout(timeout)
            self.sock.sendall((cmd + "\n").encode("utf-8"))

            deadline = time.monotonic() + timeout
            data = b""
            while time.monotonic() < deadline:
                try:
                    chunk = self.sock.recv(128)
                    if not chunk:
                        self._close_socket(emit_signal=True)
                        return None
                    data += chunk
                    if b"\n" in data:
                        break
                except socket.timeout:
                    break

            return data.decode("utf-8", errors="ignore").strip() or None
        except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
            self.connection_error.emit(f"连接断开: {e}")
            self._close_socket(emit_signal=True)
            return None
        except Exception as e:
            self.connection_error.emit(f"通信失败: {e}")
            return None

    def _handle_user_response(self, cmd: str, label: str, ok: bool, resp):
        # 喷雾开关有些 ESP 固件可能返回 OK，也可能返回简短状态；只要有响应就认为链路正常。
        if cmd in {"LEFT_ON", "LEFT_OFF", "RIGHT_ON", "RIGHT_OFF"} and resp:
            ok = True

        if ok:
            self.status_message.emit(f"{label}完成")
        else:
            self.status_message.emit(f"{label}失败")
        self.command_finished.emit(cmd, ok)

    def _handle_water_response(self, resp):
        if not resp:
            return
        try:
            parts = resp.split(",")
            if len(parts) != 2:
                raise ValueError(resp)
            self.left_water_updated.emit(float(parts[0]))
            self.right_water_updated.emit(float(parts[1]))
        except ValueError:
            self.status_message.emit("水位数据格式错误")

    def _close_socket(self, emit_signal: bool):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
            if emit_signal:
                self.disconnected.emit()

    def close(self):
        self.water_timer.stop()
        self._reconnect_timer.stop()
        self._stop_event.set()
        self._cmd_queue.put((0, next(self._seq), "_STOP", "", False, "internal"))
        self._close_socket(emit_signal=False)
        if self._worker.is_alive():
            self._worker.join(timeout=1.0)
