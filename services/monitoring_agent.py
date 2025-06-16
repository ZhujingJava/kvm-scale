import libvirt
import json


def get_vm_resource_usage(domain: libvirt.virDomain):
    """
    通过 libvirt API 获取虚拟机的资源使用情况。
    这对于判断虚拟机是否“空闲”至关重要。

    :param domain: libvirt 的 Domain 对象。
    :return: 包含资源使用信息的字典，或在失败时返回 None。
    """
    try:
        # 1. 获取内存使用情况 (需要 virtio_balloon 驱动)
        mem_stats = domain.memoryStats()
        total_mem_kb = mem_stats.get('actual', 0)
        unused_mem_kb = mem_stats.get('unused', 0)

        if total_mem_kb == 0:
            # 无法获取有效的内存信息
            return None

        # 计算内存使用率
        mem_usage_percent = ((total_mem_kb - unused_mem_kb) / total_mem_kb) * 100

        # 2. 获取 vCPU 数量
        # 注意：精确的客户机 CPU 使用率需要复杂的采样计算。
        # 在我们的场景中，我们主要关心内存使用率来判断是否空闲，所以这里简化处理。
        current_vcpu = domain.info()[3]

        return {
            "memory_usage_percent": round(mem_usage_percent, 2),
            "current_vcpu": current_vcpu,
            "total_memory_mb": total_mem_kb // 1024
        }
    except libvirt.libvirtError:
        # 可能是 Guest Agent 未运行或不支持该命令, 或者VM没有气球设备
        # 在这种情况下，我们无法判断其是否空闲，所以返回 None
        return None