# src/spray_controller.py
import socket
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

class SprayController(QObject):
    voltage_updated = pyqtSignal(float)
    connection_error = pyqtSignal(str)
    pwm_config_received = pyqtSignal(dict)  # PWM配置响应

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

    # PWM控制方法
    def set_pwm_duty(self, duty_percent):
        """设置PWM占空比（0-100）"""
        if 0 <= duty_percent <= 100:
            self._send_cmd(f"SET_DUTY {duty_percent}")
            return True
        return False

    def set_pwm_frequency(self, freq_hz):
        """设置PWM频率（Hz）"""
        if 100 <= freq_hz <= 50000:  # 合理范围100Hz-50kHz
            self._send_cmd(f"SET_FREQ {freq_hz}")
            return True
        return False

    def set_voltage_boost(self, boost_percent):
        """设置电压提升百分比（0-50）"""
        if 0 <= boost_percent <= 50:
            self._send_cmd(f"SET_BOOST {boost_percent}")
            return True
        return False

    def enable_continuous_mode(self):
        """启用连续喷雾模式（可能提高平均电压）"""
        self._send_cmd("MODE_CONTINUOUS")

    def enable_pulse_mode(self, pulse_width_ms=100):
        """启用脉冲喷雾模式"""
        self._send_cmd(f"MODE_PULSE {pulse_width_ms}")

    def get_pwm_config(self):
        """查询当前PWM配置"""
        self._send_cmd("GET_PWM_CONFIG")

    def set_motor_enable(self, enable=True):
        """使能/禁用电机"""
        cmd = "MOTOR_ENABLE 1" if enable else "MOTOR_ENABLE 0"
        self._send_cmd(cmd)

    def overdrive_start(self, duration_ms=100, duty_percent=100):
        """过驱动启动：短暂施加高占空比"""
        # 先设置高占空比
        self.set_pwm_duty(duty_percent)
        # 设置定时器恢复正常
        QTimer.singleShot(duration_ms, lambda: self.set_pwm_duty(80))

    def _request_voltage(self):
        if not self.sock:
            return
        try:
            self.sock.send("GET_VOLTAGE\n".encode())
            data = self.sock.recv(1024).decode().strip()

            # 检查是否是PWM配置响应
            if data.startswith("PWM_CONFIG:"):
                # 解析PWM配置
                config_str = data[11:]  # 去掉"PWM_CONFIG:"前缀
                config = self._parse_pwm_config(config_str)
                self.pwm_config_received.emit(config)
            else:
                # 尝试解析为电压值
                try:
                    voltage = float(data.replace('V', ''))
                    self.voltage_updated.emit(voltage)
                except ValueError:
                    # 可能是其他响应，忽略
                    pass
        except Exception as e:
            self.connection_error.emit(f"数据读取失败: {e}")
            self.sock = None

    def _parse_pwm_config(self, config_str):
        """解析PWM配置字符串"""
        config = {}
        try:
            # 假设格式为: "duty:80,freq:10000,boost:0,mode:continuous"
            parts = config_str.split(',')
            for part in parts:
                key, value = part.split(':')
                config[key.strip()] = value.strip()
        except:
            pass
        return config

    def close(self):
        if self.sock:
            self.sock.close()
        self.volt_timer.stop()