from flask import Flask, request, jsonify, render_template_string
import datetime

app = Flask(__name__)

latest_data = {
    "device_id": "",
    "tcp_connected": False,
    "battery": -1,
    "left_water": -1,
    "right_water": -1,
    "status": "unknown",
    "last_update": ""
}

# 用于浏览器显示状态的简单 HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>指挥中心模拟</title>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="2">
    <style>
        body { font-family: Arial; padding: 20px; background: #f0f0f0; }
        .card { background: white; padding: 20px; border-radius: 10px; max-width: 400px; margin: 20px auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .good { color: green; font-weight: bold; }
        .bad { color: red; font-weight: bold; }
        h2 { text-align: center; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🤖 机器人状态</h2>
        <p>设备ID: <strong>{{ data.device_id }}</strong></p>
        <p>底盘连接: 
            {% if data.tcp_connected %}
                <span class="good">正常</span>
            {% else %}
                <span class="bad">断开</span>
            {% endif %}
        </p>
        <p>电池电量: <strong>{{ data.battery }}%</strong></p>
        <p>左液量: <strong>{{ data.left_water }}%</strong></p>
        <p>右液量: <strong>{{ data.right_water }}%</strong></p>
        <p>状态: <strong>{{ data.status }}</strong></p>
        <p>最后更新: <strong>{{ data.last_update }}</strong></p>
    </div>
</body>
</html>
"""

@app.route('/api/robot/status', methods=['POST'])
def receive_status():
    global latest_data
    data = request.get_json()
    if data:
        latest_data = {
            "device_id": data.get("device_id", ""),
            "tcp_connected": data.get("tcp_connected", False),
            "battery": data.get("battery", -1),
            "left_water": data.get("left_water", -1),
            "right_water": data.get("right_water", -1),
            "status": data.get("status", "unknown"),
            "last_update": datetime.datetime.now().strftime("%H:%M:%S")
        }
        print(f"收到上报数据: {data}")
        return jsonify({"code": 200, "message": "ok"})
    return jsonify({"code": 400, "message": "invalid data"}), 400

@app.route('/', methods=['GET'])
def show_status():
    return render_template_string(HTML_TEMPLATE, data=latest_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)