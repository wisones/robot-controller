import socket

esp_ip = "192.168.10.200"
esp_port = 8266

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(3)

try:
    sock.connect((esp_ip, esp_port))
    print("连接成功")
    # 测试左喷开
    sock.send(b"LEFT_ON\n")
    print("发送 LEFT_ON")
    # 等待返回（如果ESP代码有返回）
    try:
        resp = sock.recv(64)
        print("回复:", resp.decode())
    except:
        pass

    # 2秒后关闭
    import time
    time.sleep(2)
    sock.send(b"LEFT_OFF\n")
    print("发送 LEFT_OFF")
    sock.close()
except Exception as e:
    print("连接失败:", e)