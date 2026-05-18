import socket

esp_ip = "192.168.10.200"
esp_port = 8266

def send_cmd(cmd):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((esp_ip, esp_port))
        s.send((cmd + "\n").encode())
        resp = s.recv(64).decode().strip()
        print(f"发送: {cmd}  → 回复: {resp}")
    except Exception as e:
        print(f"失败: {e}")
    finally:
        s.close()

# 测试命令
send_cmd("GET_WATER")
send_cmd("TARE_LEFT")
send_cmd("SET_LEFT_FULL")