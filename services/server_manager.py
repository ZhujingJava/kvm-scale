# services/server_manager.py
import os
import yaml


def get_server_list():
    """
    读取项目根目录下 config.yaml 文件中的服务器 IP 列表。
    """
    # 获取当前文件的目录的上级目录路径，然后拼接 config.yaml
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.yaml'))

    if not os.path.exists(config_path):
        print(f"配置文件不存在: {config_path}")
        return []

    with open(config_path, 'r', encoding='utf-8') as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"YAML 解析错误: {e}")
            return []

    servers_config = config.get('servers', {})
    if isinstance(servers_config, dict):
        # 返回一个由服务器 IP 地址组成的简单列表
        return list(servers_config.keys())
    else:
        print("配置中的 'servers' 字段格式不正确，应为一个字典。")
        return []