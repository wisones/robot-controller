import socket, time

esp_ip = "192.168.10.200"
esp_port = 8266

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect((esp_ip, esp_port))
    print("Connected")
    s.sendall(b"LEFT_ON\n")
    time.sleep(0.2)  # 等待 ESP 处理
    resp = s.recv(64).decode().strip()
    print("Response:", resp)
    s.close()
except socket.timeout:
    print("Connection or read timed out")
except ConnectionRefusedError:
    print("Connection refused – ESP not listening on port 8266")
except Exception as e:
    print("Error:", e)