# services/host_monitor.py

import psutil

def get_local_host_stats():
    """
    获取本机的 CPU 和 内存使用情况（用于测试）
    """
    cpu_percent = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    return {
        "cpu_percent": cpu_percent,
        "mem_total": mem.total // 1024,     # KB
        "mem_available": mem.available // 1024,
        "mem_used_percent": mem.percent
    }
