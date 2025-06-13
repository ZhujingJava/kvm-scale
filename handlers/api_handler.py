# handlers/api_handler.py

from flask import Blueprint, request, jsonify, render_template
import yaml
import os
from services.server_manager import get_all_servers
from services.kvm_inspector import get_all_vms_info
import psutil
import socket
import paramiko
import time  # 确保文件顶部已导入 time 模块
api_bp = Blueprint('api', __name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
with open(CONFIG_PATH, "r") as f:
    CONFIG = yaml.safe_load(f)



# 全局缓存变量
_cached_servers_data = None
_cache_expiration = 0
CACHE_TTL = 300  # 缓存时间：5分钟（单位秒）

def get_servers_data(force_refresh=False):
    global _cached_servers_data, _cache_expiration

    if not force_refresh and time.time() < _cache_expiration:
        return _cached_servers_data

    servers = get_all_servers()
    for server in servers:
        cpu_usage = get_server_cpu_usage(server['ip'])
        disk_usage = get_server_disk_usage(server['ip'])
        memory_usage = get_server_memory_usage(server['ip'])
        server['cpu_usage'] = cpu_usage
        server['disk_usage'] = disk_usage
        server['memory_usage'] = memory_usage

    # 更新缓存
    _cached_servers_data = {"servers": servers}
    _cache_expiration = time.time() + CACHE_TTL

    return _cached_servers_data


@api_bp.route('/servers', methods=['GET'])
def list_servers():
    data = get_servers_data()
    return jsonify(data)


# 获取服务器的CPU使用率
def get_server_cpu_usage(ip):
    if ip == socket.gethostbyname(socket.gethostname()):
        # 本地服务器
        return psutil.cpu_percent(interval=1)
    else:
        return _get_remote_metric(ip, """
            top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'
        """)

# 获取服务器的内存使用率
def get_server_memory_usage(ip):
    if ip == socket.gethostbyname(socket.gethostname()):
        # 本地服务器
        return psutil.virtual_memory().percent
    else:
        return _get_remote_metric(ip, """
            free | grep Mem | awk '{printf "%.2f", ($3 / $2) * 100}'
        """)

def get_server_disk_usage(ip):
    if ip == socket.gethostbyname(socket.gethostname()):
        # 本地服务器：获取 / 分区的使用率
        return psutil.disk_usage('/').percent
    else:
        return _get_remote_metric(ip, """
            df -h --exclude-type=fuse.gvfsd-fuse  | awk '$1 ~ "^/dev/" && ($6 == "/" || $6 == "/home") {max=($5>max ? $5:max)} END{print max}' | tr -d '%'
        """)

# 封装远程执行命令逻辑（统一使用默认私钥 + 可选SSH端口）
def _get_remote_metric(ip, cmd: str):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # 统一使用默认用户名和私钥路径
        username = CONFIG.get('default_ssh_username', 'root')
        key_path = os.path.expanduser(CONFIG.get('default_ssh_key_path', '~/.ssh/id_rsa'))

        # 检查该服务器是否配置了自定义 SSH 端口
        server_config = CONFIG['servers'].get(ip, {})
        ssh_port = server_config.get('ssh_port', 22)  # 默认22，可覆盖

        # 加载私钥
        private_key = paramiko.RSAKey(filename=key_path)

        # 建立连接
        ssh.connect(hostname=ip, port=ssh_port, username=username, pkey=private_key)

        stdin, stdout, stderr = ssh.exec_command(cmd.strip())
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        ssh.close()

        if error:
            raise Exception(f"Remote command error: {error}")

        return float(output)

    except Exception as e:
        print(f"Error fetching metric from {ip}: {e}")
        return None

@api_bp.route('/kvm/list', methods=['GET'])
def list_kvm_vms():
    host_ip = request.args.get('host')
    # 当没有 host 参数时，我们仍然可以渲染页面，但可能是个空列表或提示
    if not host_ip:
        # 即使没有 host_ip，也渲染页面并标记导航
        return render_template('kvm_list.html', host_ip=None, vms=[], active_page='kvm_list')

    try:
        vms = get_all_vms_info(host_ip)
        # --- 修改开始 --- #
        # 传递 active_page 变量到模板
        return render_template('kvm_list.html', host_ip=host_ip, vms=vms, active_page='kvm_list')
        # --- 修改结束 --- #
    except Exception as e:
        # 出错时也可以考虑渲染错误页面，并标记导航
        return render_template('kvm_list.html', error=str(e), active_page='kvm_list')
