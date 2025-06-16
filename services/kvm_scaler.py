# services/kvm_scaler.py
import libvirt
from .kvm_inspector import connect_libvirt


def adjust_vcpu(host_ip: str, vm_uuid: str, vcpu_count: int):
    """
    动态调整虚拟机的 vCPU 数量。
    注意：需要虚拟机支持 CPU hotplug。

    :param host_ip: KVM 主机 IP。
    :param vm_uuid: 虚拟机的 UUID。
    :param vcpu_count: 调整后的 vCPU 数量。
    :return: 成功返回 True，失败返回 False。
    """
    conn = None
    try:
        conn = connect_libvirt(host_ip)
        domain = conn.lookupByUUIDString(vm_uuid)
        if not domain:
            raise Exception(f"VM with UUID {vm_uuid} not found on host {host_ip}")

        # 设置 vCPU 数量（需要 LIVE 标志才能热调整）
        # VIR_DOMAIN_VCPU_MAXIMUM: 设置最大vCPU数
        # VIR_DOMAIN_AFFECT_LIVE: 应用于正在运行的虚拟机
        # VIR_DOMAIN_AFFECT_CONFIG: 更新持久化配置
        flags = libvirt.VIR_DOMAIN_AFFECT_LIVE | libvirt.VIR_DOMAIN_AFFECT_CONFIG
        domain.setVcpusFlags(vcpu_count, flags)

        print(f"Successfully set vCPU count for VM {vm_uuid} to {vcpu_count}")
        return True
    except libvirt.libvirtError as e:
        print(f"Error adjusting vCPU for VM {vm_uuid} on {host_ip}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def adjust_memory(host_ip: str, vm_uuid: str, memory_mb: int):
    """
    动态调整虚拟机的内存大小。
    注意：需要虚拟机启用弹性内存（气球驱动）。

    :param host_ip: KVM 主机 IP。
    :param vm_uuid: 虚拟机的 UUID。
    :param memory_mb: 调整后的内存大小 (MB)。
    :return: 成功返回 True，失败返回 False。
    """
    conn = None
    try:
        conn = connect_libvirt(host_ip)
        domain = conn.lookupByUUIDString(vm_uuid)
        if not domain:
            raise Exception(f"VM with UUID {vm_uuid} not found on host {host_ip}")

        # libvirt 需要 KiB 作为单位
        memory_kb = memory_mb * 1024

        # 设置当前内存（热调整）
        # VIR_DOMAIN_MEM_CURRENT: 设置当前内存
        flags = libvirt.VIR_DOMAIN_AFFECT_LIVE | libvirt.VIR_DOMAIN_AFFECT_CONFIG
        domain.setMemoryFlags(memory_kb, flags)

        print(f"Successfully set memory for VM {vm_uuid} to {memory_mb} MB")
        return True
    except libvirt.libvirtError as e:
        print(f"Error adjusting memory for VM {vm_uuid} on {host_ip}: {e}")
        return False
    finally:
        if conn:
            conn.close()