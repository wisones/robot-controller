import socket
import json
import struct
import base64
from PIL import Image
import io

def pack_message(cmd_dict):
    json_str = json.dumps(cmd_dict)
    data = json_str.encode('utf-8')
    length = len(data)
    return b'\x88' + struct.pack('<I', length) + data + b'\xAA'

def unpack_buffer(buf):
    """返回解析出的所有json消息列表"""
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

ip = "192.168.10.159"
port = 10000

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5)
try:
    sock.connect((ip, port))
    print("连接成功")
except Exception as e:
    print(f"连接失败: {e}")
    exit()

# 1) 获取当前地图配置
cmd = {"CMD": "CMD_GET_CURRENT_MAP_CONFIG", "MSG_TYPE": "CLIENT_REQUEST", "QUEUE_NUMBER": 1}
sock.send(pack_message(cmd))
buf = b''
while True:
    try:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
        msgs = unpack_buffer(buf)
        for msg in msgs:
            if msg.get("CMD") == "CMD_GET_CURRENT_MAP_CONFIG":
                print("当前地图配置:", json.dumps(msg, indent=2, ensure_ascii=False))
                map_name = msg.get("MAP_CURRENT_CONFIG", {}).get("STATIC_MAP_NAME", "")
                if not map_name:
                    print("没有找到地图名称，可能没有已保存的地图。")
                    sock.close()
                    exit()
                # 2) 获取地图元数据
                cmd2 = {"CMD": "CMD_GET_MAP_META_DATA", "MAP_NAME": map_name, "MSG_TYPE": "CLIENT_REQUEST", "QUEUE_NUMBER": 2}
                sock.send(pack_message(cmd2))
                # 继续接收元数据响应
                break
        if len(msgs) > 0:
            # 找到了地图配置，跳出while循环，进入等待元数据
            break
    except socket.timeout:
        print("接收超时")
        break

# 清空缓冲区，等待元数据
buf = b''
while True:
    try:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
        msgs = unpack_buffer(buf)
        for msg in msgs:
            if msg.get("CMD") == "CMD_GET_MAP_META_DATA":
                print("地图元数据:", json.dumps(msg, indent=2, ensure_ascii=False))
                # 3) 获取地图数据
                cmd3 = {"CMD": "CMD_GET_MAP_DATA", "MAP_NAME": map_name, "MSG_TYPE": "CLIENT_REQUEST", "QUEUE_NUMBER": 3}
                sock.send(pack_message(cmd3))
                break
        if len(msgs) > 0:
            break
    except socket.timeout:
        print("接收元数据超时")
        break

# 再等待地图数据
buf = b''
while True:
    try:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
        msgs = unpack_buffer(buf)
        for msg in msgs:
            if msg.get("CMD") == "CMD_GET_MAP_DATA":
                print("地图数据接收成功")
                map_data_b64 = msg.get("MAP_DATA", "")
                if map_data_b64:
                    # 解码并保存为图片方便查看
                    img_bytes = base64.b64decode(map_data_b64)
                    img = Image.open(io.BytesIO(img_bytes))
                    img.save("test_map.png")
                    print("地图已保存为 test_map.png")
                else:
                    print("地图数据为空")
                sock.close()
                exit()
        if len(msgs) > 0:
            break
    except socket.timeout:
        print("接收地图数据超时")
        break

sock.close()
print("测试结束")