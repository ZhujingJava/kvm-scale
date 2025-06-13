# app.py
from flask import Flask, render_template
from handlers.api_handler import api_bp, list_servers, get_servers_data

app = Flask(__name__)
app.register_blueprint(api_bp)


@app.route('/')
def index():
    data = get_servers_data()  # ✅ 获取原始数据
    servers = data.get("servers", [])
    return render_template('index.html', servers=servers)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5500)
