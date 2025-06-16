import os
import yaml
import paramiko
import psutil
from flask import Blueprint, jsonify, request
from functools import lru_cache
from services.server_manager import get_server_list
from services.kvm_inspector import get_all_vms_on_host

# Load configuration
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

# Cache for server metrics
METRICS_CACHE = {}
CACHE_TTL = 60  # seconds

api_bp = Blueprint('api', __name__)


def _get_remote_metric(host, command, port=22):
    """
    Helper function to get metrics from a remote host via SSH.
    """
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        username = config.get('default_ssh_username', 'root')
        key_path = os.path.expanduser(config.get('default_ssh_key_path', '~/.ssh/id_rsa'))
        private_key = paramiko.RSAKey(filename=key_path)

        ssh.connect(hostname=host, port=port, username=username, pkey=private_key, timeout=5)

        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode().strip()

        ssh.close()
        return output
    except Exception as e:
        print(f"Could not connect to {host} or run command: {e}")
        return None

    # 文件: handlers/api_handler.py


@lru_cache(maxsize=32)
def get_servers_data():
    servers = get_server_list()
    server_data = []

    # --- 修正后的 CPU 计算命令 ---
    # 这条命令会采样两次/proc/stat，间隔1秒，以获得准确的CPU使用率
    cpu_command = (
        "awk -v 'OFS=\" \"' '/cpu / {for(i=2;i<=NF;i++) sum+=$i; print sum, $5}' /proc/stat "
        "&& sleep 1 && "
        "awk -v 'OFS=\" \"' '/cpu / {for(i=2;i<=NF;i++) sum+=$i; print sum, $5}' /proc/stat"
    )

    for server_ip in servers:
        server_config = config.get('servers', {}).get(server_ip, {})
        ssh_port = server_config.get('ssh_port', 22)

        # --- 获取 CPU ---
        cpu_output = _get_remote_metric(server_ip, cpu_command, port=ssh_port)
        cpu_usage = "N/A"
        if cpu_output:
            try:
                # 解析两次采样的结果
                lines = cpu_output.splitlines()
                if len(lines) == 2:
                    start = [int(n) for n in lines[0].split()]
                    end = [int(n) for n in lines[1].split()]
                    total_diff = end[0] - start[0]
                    idle_diff = end[1] - start[1]
                    if total_diff > 0:
                        usage_percent = (total_diff - idle_diff) * 100.0 / total_diff
                        cpu_usage = f"{usage_percent:.2f}%"
            except (ValueError, IndexError, ZeroDivisionError) as e:
                print(f"Error parsing CPU usage for {server_ip}: {e}")

        # --- 获取内存 ---
        mem_info = _get_remote_metric(server_ip, "free -m | grep Mem | awk '{print $3\"/\"$2 \" MB\"}'", port=ssh_port)

        # --- 新增：获取磁盘 ---
        disk_info = _get_remote_metric(server_ip, "df -h / | awk 'NR==2 {print $3\"/\"$2\" (\"$5\")\"}'", port=ssh_port)

        server_data.append({
            "ip": server_ip,
            "cpu": cpu_usage,
            "memory": mem_info or "N/A",
            "disk": disk_info or "N/A",  # 新增磁盘字段
            "status": "active" if cpu_output else "offline"
        })

    return {"servers": server_data}
@api_bp.route('/servers')
def list_servers():
    data = get_servers_data()
    return jsonify(data)


@api_bp.route('/kvm/list')
def list_kvm_vms():
    host_ip = request.args.get('host')
    if not host_ip:
        return jsonify({"error": "Host IP is required"}), 400

    try:
        vms = get_all_vms_on_host(host_ip)
        return jsonify(vms)
    except Exception as e:
        # This will catch libvirt connection errors and other issues
        return jsonify({"error": f"Failed to get VM list from {host_ip}: {str(e)}"}), 500