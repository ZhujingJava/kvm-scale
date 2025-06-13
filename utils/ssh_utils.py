# D:/kvm-resource-controller/utils/ssh_utils.py

# 确保已安装 paramiko：pip install paramiko
import paramiko
from paramiko import AutoAddPolicy, SSHClient

from services.kvm_inspector import CONFIG


def run_ssh_command(host_ip, command):
    server = CONFIG['servers'].get(host_ip)
    ssh_conf = server['ssh_config']

    with SSHClient() as client:
        client.set_missing_host_key_policy(AutoAddPolicy())
        client.connect(
            hostname=ssh_conf['hostname'],
            username=ssh_conf['username'],
            key_filename=ssh_conf['key_filename']
        )
        stdin, stdout, stderr = client.exec_command(command)
        return stdout.read().decode(), stderr.read().decode()
