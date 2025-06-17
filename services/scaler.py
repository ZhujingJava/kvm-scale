# services/scaler.py

import subprocess
import logging

logger = logging.getLogger(__name__)

def scale_vm_cpu(vm_name, host_ip, new_cpu_count):
    """
    调整虚拟机 CPU 数量（需支持热插拔）
    """
    logger.info(f"Scaling VM {vm_name} on {host_ip} to {new_cpu_count} CPUs")

    cmd = f"ssh root@{host_ip} 'virsh setvcpus {vm_name} {new_cpu_count} --live --config'"
    return run_command(cmd)


def scale_vm_memory(vm_name, host_ip, new_mem_gb):
    """
    调整虚拟机内存（需支持弹性内存）
    """
    logger.info(f"Scaling VM {vm_name} on {host_ip} to {new_mem_gb} GB memory")

    # 注意：单位转换为 MB
    mem_mb = new_mem_gb * 1024
    cmd = f"ssh root@{host_ip} 'virsh setmem {vm_name} {mem_mb}M --live --config'"
    return run_command(cmd)


def run_command(cmd):
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            logger.info(f"Command succeeded: {result.stdout}")
            return True
        else:
            logger.error(f"Command failed: {result.stderr}")
            return False
    except Exception as e:
        logger.exception(f"Error executing command: {e}")
        return False
