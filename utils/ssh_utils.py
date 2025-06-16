# utils/ssh_utils.py
import paramiko
import os
import yaml

# 加载一次配置，避免重复读取
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
with open(CONFIG_PATH, "r") as f:
    CONFIG = yaml.safe_load(f)


def run_ssh_command(host_ip: str, command: str) -> tuple[str, str]:
    """
    连接到远程服务器并执行命令。

    :param host_ip: 目标服务器的 IP 地址。
    :param command: 要执行的 Shell 命令。
    :return: 一个元组，包含 (stdout, stderr)。
    :raises: 如果连接或执行出错，则会抛出异常。
    """
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        username = CONFIG.get('default_ssh_username', 'root')
        key_path = os.path.expanduser(CONFIG.get('default_ssh_key_path', '~/.ssh/id_rsa'))

        server_config = CONFIG.get('servers', {}).get(host_ip, {})
        ssh_port = server_config.get('ssh_port', 22)

        private_key = paramiko.RSAKey(filename=key_path)

        ssh.connect(hostname=host_ip, port=ssh_port, username=username, pkey=private_key, timeout=10)

        stdin, stdout, stderr = ssh.exec_command(command.strip())
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()

        ssh.close()

        if error:
            # 对于某些命令，错误输出可能是正常的（例如，grep 未找到匹配项）
            # 但在这里我们还是记录下来
            print(f"SSH command on {host_ip} produced stderr: {error}")

        return output, error

    except Exception as e:
        print(f"Error running SSH command on {host_ip}: {e}")
        raise  # 重新抛出异常，让调用者决定如何处理