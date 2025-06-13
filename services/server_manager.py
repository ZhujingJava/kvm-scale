# services/server_manager.py
def get_all_servers():
    """读取项目根目录下的 config.yaml 文件中的服务器 IP"""
    import os
    import yaml

    # 获取当前文件的目录的上两级目录路径，然后拼接 config.yaml
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
        return [{"ip": ip} for ip in servers_config]
    else:
        print("配置中的 'servers' 字段格式不正确")
        return []