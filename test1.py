import socket
import json
import struct
import time

def pack_message(cmd_dict):
    """将字典装帧：0x88 + 4字节小端长度 + JSON + 0xAA"""
    json_str = json.dumps(cmd_dict)
    data = json_str.encode('utf-8')
    length = len(data)
    return b'\x88' + struct.pack('<I', length) + data + b'\xAA'

def unpack_message(data):
    """简单解帧：找0x88...0xAA，返回json字符串列表"""
    msgs = []
    i = 0
    while i < len(data):
        if data[i] == 0x88:
            if i + 5 > len(data):
                break
            length = struct.unpack('<I', data[i+1:i+5])[0]
            total_len = 5 + length + 1
            if i + total_len > len(data):
                break
            if data[i+5+length] == 0xAA:
                json_bytes = data[i+5:i+5+length]
                try:
                    msg = json.loads(json_bytes.decode('utf-8'))
                    msgs.append(msg)
                except:
                    pass
                i += total_len
                continue
        i += 1
    return msgs

def main():
    ip = input("请输入机器人IP地址: ").strip()
    port_str = input("请输入端口 (默认9090): ").strip()
    port = int(port_str) if port_str else 9090

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)  # 连接超时5秒

    print(f"正在连接 {ip}:{port} ...")
    try:
        sock.connect((ip, port))
        print("TCP连接成功！")
    except Exception as e:
        print(f"连接失败: {e}")
        return

    # 发送CMD_GET_VERSION命令（会收到回复）
    cmd = {
        "CMD": "CMD_GET_VERSION",
        "MSG_TYPE": "CLIENT_REQUEST",
        "QUEUE_NUMBER": 1
    }
    packet = pack_message(cmd)
    try:
        sock.send(packet)
        print("已发送获取版本命令，等待回复...")
    except Exception as e:
        print(f"发送失败: {e}")
        sock.close()
        return

    # 接收回复，超时5秒
    sock.settimeout(5)
    buf = b''
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
            # 尝试解析，如果收到完整回复就退出
            msgs = unpack_message(buf)
            for msg in msgs:
                if msg.get("CMD") == "CMD_GET_VERSION":
                    print("收到回复:")
                    print(json.dumps(msg, indent=2, ensure_ascii=False))
                    sock.close()
                    return
            # 防止无限循环，简单限制接收次数
            if len(msgs) > 0:
                break
    except socket.timeout:
        print("接收超时，可能协议不匹配或底盘未响应")
    except Exception as e:
        print(f"接收出错: {e}")
    finally:
        sock.close()

    if buf:
        # 尝试解析原始数据
        print("原始数据（16进制）:", buf.hex())
        msgs = unpack_message(buf)
        if msgs:
            print("解析到的消息:")
            for msg in msgs:
                print(json.dumps(msg, indent=2, ensure_ascii=False))
        else:
            print("无法解析收到的数据")
    else:
        print("未收到任何数据")

if __name__ == "__main__":
    main()