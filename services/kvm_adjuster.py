import requests
import yaml

with open("config.yaml", "r") as f:
    CONFIG = yaml.safe_load(f)

def adjust_kvm_resources(instance_ip, cpu=None, memory=None):
    server_config = CONFIG["servers"].get(instance_ip)
    if not server_config:
        print(f"No config found for {instance_ip}")
        return

    api_url = f"http://{instance_ip}/api/v1/kvm/adjust"
    payload = {}
    if cpu:
        payload["cpu"] = cpu
    if memory:
        payload["memory"] = memory
    headers = {
        "Authorization": f"Bearer {server_config['api_token']}"
    }
    response = requests.post(api_url, json=payload, headers=headers)
    if response.status_code == 200:
        print(f"Successfully adjusted resources on {instance_ip}")
    else:
        print(f"Failed to adjust resources: {response.text}")
