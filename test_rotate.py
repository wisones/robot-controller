# test_rotate.py
import socket
import json
import struct
import math
import time

def pack_message(cmd_dict):
    """封装协议包"""
    json_str = json.dumps(cmd_dict)
    data = json_str.encode('utf-8')
    length = len(data)
    return b'\x88' + struct.pack('<I', length) + data + b'\xAA'

def parse_buffer(buf):
    """解析缓冲区中的完整消息"""
    msgs = []
    i = 0
    while i < len(buf):
        if buf[i] == 0x88:
            if i + 5 > len(buf):
                break
            length = struct.unpack('<I', buf[i+1:i+5])[0]
            total_len = 5 + length + 1
            if i + total_len > len(buf):
                break
            if buf[i+5+length] == 0xAA:
                json_bytes = buf[i+5:i+5+length]
                try:
                    msg = json.loads(json_bytes.decode('utf-8'))
                    msgs.append(msg)
                except:
                    pass
                i += total_len
                continue
        i += 1
    return msgs

# 连接底盘
ip = "192.168.10.159"
port = 10000
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5)
try:
    sock.connect((ip, port))
    print("✓ 连接成功")
except Exception as e:
    print(f"✗ 连接失败: {e}")
    exit()

# 1. 订阅导航状态（必须，否则可能收不到完成通知）
sub_cmd = {"CMD": "CMD_SUB_NAVI", "MSG_TYPE": "CLIENT_REQUEST", "QUEUE_NUMBER": 1}
sock.send(pack_message(sub_cmd))
print("已订阅导航状态")

# 2. 发送旋转指令（测试目标角度：0 弧度，即朝向 X 轴正方向）
target_angle_rad = math.radians(90)   # 可改为 math.radians(90) 等测试
rotate_cmd = {
    "CMD": "CMD_NAV_ROTATE_TO",
    "MSG_TYPE": "CLIENT_REQUEST",
    "QUEUE_NUMBER": 2,
    "ANGLE": target_angle_rad
}
print(f"发送旋转命令，目标角度 = {target_angle_rad} 弧度 ({math.degrees(target_angle_rad)}°)")
sock.send(pack_message(rotate_cmd))

# 3. 等待反馈（响应或导航状态更新）
buffer = b''
start_time = time.time()
while time.time() - start_time < 15:
    try:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buffer += chunk
        msgs = parse_buffer(buffer)
        for msg in msgs:
            cmd = msg.get("CMD", "")
            if cmd == "CMD_NAV_ROTATE_TO" and msg.get("MSG_TYPE") == "SERVER_RESPONSE":
                print("收到旋转命令响应:", json.dumps(msg, indent=2, ensure_ascii=False))
            elif cmd == "CMD_PUB_NAVI":
                navi_info = msg.get("NAVI_INFO", {})
                status = navi_info.get("TASK_STATUS", "")
                print(f"导航状态: {status}")
                if status == "COMPLETED":
                    print("✓ 旋转任务完成")
                    sock.close()
                    exit()
    except socket.timeout:
        continue
    except Exception as e:
        print("接收异常:", e)
        break

print("超时：未在15秒内接收到旋转完成信号")
sock.close()