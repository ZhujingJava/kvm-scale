from flask import Flask, render_template, request  # <-- 已在此处添加 request
from handlers.api_handler import api_bp, get_servers_data
import logging

app = Flask(__name__)

# 配置日志，以便在控制台看到信息
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

# 注册 API 蓝图，并添加 /api 前缀
app.register_blueprint(api_bp, url_prefix='/api')


@app.route('/')
def index():
    """渲染主页面，显示服务器列表。"""
    try:
        data = get_servers_data()
        servers = data.get("servers", [])
    except Exception as e:
        app.logger.error(f"Error getting server data for index page: {e}")
        servers = []
    return render_template('index.html', servers=servers, active_page='servers')


@app.route('/kvm/list')
def kvm_list_page():
    """
    渲染 KVM 虚拟机列表页面。
    页面本身只提供一个框架，具体数据由前端 JavaScript 通过 API 获取。
    """
    # 从 URL 参数中获取 host_ip，用于传递给模板
    host_ip = request.args.get('host')
    return render_template('kvm_list.html', host_ip=host_ip, vms=[], active_page='kvm_list')


if __name__ == '__main__':
    # 在生产环境中，应使用 Gunicorn 或 uWSGI 等 WSGI 服务器
    # 'use_reloader=True' 在调试时非常有用，但对于我们之前的后台线程场景是不兼容的
    app.run(debug=True, host='0.0.0.0', port=5500, use_reloader=True)