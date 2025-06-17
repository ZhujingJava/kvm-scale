# services/vm_locator.py

import logging
import redis

logger = logging.getLogger(__name__)

# Redis 连接配置
redis_client = redis.StrictRedis(
    host='localhost',  # 替换为你的 Redis 地址
    port=6379,
    db=0,
    decode_responses=True
)

KVMMAP_KEY = "kvm_host_map"

def find_host_by_vm_ip(vm_ip):
    """
    根据虚拟机 IP 查找宿主机地址。

    支持：
      - 从 Redis 中获取映射关系
      - 或者通过 ARP 表动态查找（需 root 权限）
    """
    logger.info(f"Looking up host for VM IP: {vm_ip}")

    # 方法一：从 Redis 获取映射
    host_ip = redis_client.hget(KVMMAP_KEY, vm_ip)
    if host_ip:
        logger.info(f"Found host via Redis: {host_ip}")
        return host_ip

    # 方法二：尝试通过本地 ARP 表查找（适用于同网段）
    try:
        import subprocess
        arp_output = subprocess.check_output(["arp", "-n", vm_ip], stderr=subprocess.DEVNULL, text=True)
        for line in arp_output.splitlines():
            if "ether" in line and vm_ip in line:
                parts = line.strip().split()
                mac_address = parts[2]
                logger.info(f"Found MAC address for {vm_ip}: {mac_address}")
                # TODO: 根据 MAC 地址查归属宿主机（需要额外配置）
                return None  # 暂不实现自动 MAC → 宿主匹配
    except Exception as e:
        logger.warning(f"ARP lookup failed for {vm_ip}: {e}")

    logger.warning(f"No host found for VM {vm_ip}")
    return None
