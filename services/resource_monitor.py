# services/resource_monitor.py
import psutil
import socket
import paramiko
import yaml
import os

def get_local_cpu_usage():
    """获取本机 CPU 使用率"""
    return psutil.cpu_percent(interval=1)

def get_local_memory_usage():
    """获取本机内存使用率"""
    return psutil.virtual_memory().percent

def get_local_disk_usage():
    """获取本机磁盘使用率"""
    return psutil.disk_usage('/').percent

def get_remote_cpu_usage(ip, config):
    """获取远程主机 CPU 使用率"""
    return _get_remote_metric(ip, config, """
        top -bn1 | grep 'Cpu(s)' | sed 's/.*, *\$[0-9.]*\$%* id.*/\\1/' | awk '{print 100 - $1}'
    """)

def get_remote_memory_usage(ip, config):
    """获取远程主机内存使用率"""
    return _get_remote_metric(ip, config, """
        free | grep Mem | awk '{print ($3 / $2) * 100}'
    """)

def get_remote_disk_usage(ip, config):
    """获取远程主机磁盘使用率"""
    return _get_remote_metric(ip, config, """
        df -h / | awk 'NR==2 {print $5}' | tr -d '%'
    """)

def _get_remote_metric(ip, config, cmd: str):
    """封装远程执行命令逻辑"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # 从配置中读取 SSH 用户和私钥路径
        server_config = config.get('servers', {}).get(ip, {})
        username = server_config.get('ssh_username', config.get('default_ssh_username', 'root'))
        key_path = server_config.get('ssh_key_path') or config.get('default_ssh_key_path')

        if not key_path:
            raise Exception("No SSH key path configured")

        # 加载私钥
        private_key = paramiko.RSAKey(filename=key_path)

        # 建立连接
        ssh.connect(hostname=ip, username=username, pkey=private_key)

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
