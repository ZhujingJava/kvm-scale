# handlers/api_handler.py

import os
import asyncio
import asyncssh
from datetime import datetime, timedelta
import yaml
from flask import Blueprint, jsonify, request
import threading
import time
from services.kvm_inspector import get_all_vms_on_host
from services.server_manager import get_server_list

# Load configuration
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

# Cache for server metrics with timestamp control
SERVER_CACHE = {
    "data": None,
    "timestamp": None
}
CACHE_TTL = 180  # seconds

api_bp = Blueprint('api', __name__)



@api_bp.route('/kvm/list')
def list_kvm_vms():
    host_ip = request.args.get('host')
    if not host_ip:
        return jsonify({"error": "Host IP is required"}), 400

    try:
        vms = get_all_vms_on_host(host_ip)
        return jsonify(vms)
    except Exception as e:
        print(f"[ERROR] Failed to get VM list from {host_ip}: {str(e)}")
        return jsonify({"error": f"Failed to get VM list from {host_ip}"}), 500
async def _async_get_remote_metric(host, command, port=22, retries=3):
    import textwrap

    cmd = textwrap.dedent(command).strip()

    username = config.get('default_ssh_username', 'root')
    key_path = os.path.expanduser(config.get('default_ssh_key_path', '~/.ssh/id_rsa'))

    for attempt in range(retries):
        try:
            async with asyncssh.connect(
                host, port=port,
                username=username,
                client_keys=[key_path],
                known_hosts=None
            ) as conn:

                result = await conn.run(cmd, check=True)
                return result.stdout.strip()
        except Exception as e:
            print(f"[ERROR] SSH connection failed for {host} (attempt {attempt+1}/{retries}): {e}")
            await asyncio.sleep(1)
    return None


async def _collect_single_server(server_ip, server_config):
    ssh_port = server_config.get('ssh_port', 22)

    # 同时发起多个命令
    cpu_task = _async_get_remote_metric(
        server_ip,
        "grep '^cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {printf \"%.2f%%\", usage}'",
        port=ssh_port
    )

    mem_task = _async_get_remote_metric(
        server_ip,
        "free -m | grep Mem | awk '{print $3,$2}'",
        port=ssh_port
    )

    disk_task = _async_get_remote_metric(
        server_ip,
        """
        df -h --output=source,target,size,used,pcent 2>/dev/null |
        awk '$1 ~ /^\\/dev\\// && $2 !~ /^\\/(boot|media)/ && $1 !~ /swap/ {
            gsub(/%/, "", $5);
            print $2, $3, $4, $5
        }'
        """,
        port=ssh_port
    )


    cpu_str, mem_output, disk_output = await asyncio.gather(cpu_task, mem_task, disk_task)

    # Parse CPU
    cpu_percent = float(cpu_str.strip('%')) if cpu_str and cpu_str != "N/A" else 0.0

    # Parse Memory
    mem_used_mb, mem_total_mb = 0, 0
    if mem_output:
        try:
            used, total = map(int, mem_output.split())
            mem_used_mb = used
            mem_total_mb = total
        except:
            pass
    mem_usage_percent = round(mem_used_mb * 100.0 / mem_total_mb, 2) if mem_total_mb else 0

    # Parse Disk
    # Parse Disk Info (Multiple Mount Points)
    disk_info = []
    if disk_output:
        try:
            for line in disk_output.strip().splitlines():
                if not line.strip():
                    continue
                parts = line.split()
                mount_point = parts[0]
                total = parts[1]
                used = parts[2]
                percent = int(parts[3])

                # 单位转换 G/T -> GB
                def parse_size(s):
                    if s.endswith("G"):
                        return float(s[:-1])
                    elif s.endswith("T"):
                        return float(s[:-1]) * 1024
                    elif s.endswith("M"):
                        return float(s[:-1]) / 1024
                    else:
                        return float(s) / 1024 / 1024  # KB to GB

                total_gb = round(parse_size(total), 2)
                used_gb = round(parse_size(used), 2)

                disk_info.append({
                    "mount_point": mount_point,
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "usage_percent": percent
                })
        except Exception as e:
            print(f"[WARN] Failed to parse disk info: {e}")

    return {
        "ip": server_ip,
        "cpu_percent": cpu_percent,
        "mem_used_mb": mem_used_mb,
        "mem_total_mb": mem_total_mb,
        "mem_usage_percent": mem_usage_percent,
        "disk_info": disk_info,  # 👈 新增字段
        "status": "active" if cpu_percent > 0 else "offline"
    }


async def _collect_all_servers(servers):
    tasks = []
    for server_ip in servers:
        server_config = config.get('servers', {}).get(server_ip, {})
        task = _collect_single_server(server_ip, server_config)
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return {"servers": list(results)}
def _background_cache_updater():
    while True:
        try:
            servers = get_server_list()
            loop = asyncio.new_event_loop()
            data = loop.run_until_complete(_collect_all_servers(servers))
            global SERVER_CACHE
            SERVER_CACHE = {
                "data": data,
                "timestamp": datetime.now()
            }
            print("[INFO] Server metrics cache updated.")
        except Exception as e:
            print(f"[ERROR] Failed to update server metrics: {e}")
        time.sleep(CACHE_TTL //2)  # 每隔一半 TTL 更新一次

# 启动后台采集线程
threading.Thread(target=_background_cache_updater, daemon=True).start()

def get_servers_data():
    global SERVER_CACHE
    now = datetime.now()

    # Check cache validity
    if SERVER_CACHE["data"] and SERVER_CACHE["timestamp"]:
        if (now - SERVER_CACHE["timestamp"]).total_seconds() < CACHE_TTL:
            return SERVER_CACHE["data"]

    servers = get_server_list()
    loop = asyncio.new_event_loop()
    data = loop.run_until_complete(_collect_all_servers(servers))

    SERVER_CACHE = {
        "data": data,
        "timestamp": now
    }

    return data
