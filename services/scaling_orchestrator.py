# services/scaling_orchestrator.py
import libvirt
from . import kvm_inspector, scaler, monitoring_agent, server_manager


def handle_scaling_request(vm_name: str, host_ip: str, alert: dict):
    """
    根据告警编排完整的虚拟机资源伸缩流程。
    这是你描述的 6 步逻辑的核心实现。
    """
    # [1] 告警已触发 (由调用方完成)
    print(f"--- Starting Scaling Orchestration for VM '{vm_name}' on Host '{host_ip}' ---")

    conn = None
    try:
        conn = kvm_inspector.connect_libvirt(host_ip)
        if not conn:
            return {"status": "error", "message": f"Could not connect to libvirt on {host_ip}"}

        # 通过名称查找目标虚拟机
        try:
            target_domain = conn.lookupByName(vm_name)
        except libvirt.libvirtError:
            return {"status": "error", "message": f"VM '{vm_name}' not found on host '{host_ip}'"}

        # [2] 判断 vm01 当前资源与最大限制
        policy = kvm_inspector.get_vm_policy_from_metadata(target_domain)
        current_vcpu = target_domain.info()[3]
        max_vcpu = policy.get('max_vcpu', current_vcpu)
        scale_step_cpu = policy.get('scale_step_cpu', 1)

        if current_vcpu >= max_vcpu:
            return {"status": "skipped", "message": f"VM '{vm_name}' is already at its max vCPU limit ({max_vcpu})."}

        needed_cpus = scale_step_cpu
        print(f"Step [2]: VM '{vm_name}' needs {needed_cpus} more vCPU(s). Current: {current_vcpu}, Max: {max_vcpu}.")

        # [3] 判断宿主机剩余资源是否可扩容
        if kvm_inspector.check_host_has_enough_resources(conn, needed_cpus):
            print(f"Step [3]: Host '{host_ip}' has enough resources.")
            # [6] 执行扩容
            new_vcpu_count = current_vcpu + needed_cpus
            print(f"Step [6]: Scaling up '{vm_name}' to {new_vcpu_count} vCPUs...")
            success = scaler.adjust_vcpu(host_ip, target_domain.UUIDString(), new_vcpu_count)
            return {"status": "success" if success else "error", "action": "scaled_up_directly"}

        # [4] 宿主机资源不足 -> 找可降级的 VM
        print(f"Step [3/4]: Host '{host_ip}' has insufficient resources. Finding victim VMs to compress...")

        victim_vms = _find_compressible_vms(conn, vm_name, policy.get('priority', 99))
        if not victim_vms:
            return {"status": "failed", "message": "Host has no resources, and no compressible VMs found."}

        # [5] 动态压缩它们，释放资源
        freed_cpus = 0
        for victim in victim_vms:
            if freed_cpus >= needed_cpus:
                break
            freed_cpus += _compress_vm(host_ip, victim)

        print(f"Step [5]: Freed up a total of {freed_cpus} vCPUs.")

        # [6] 回来重新判断是否够
        if kvm_inspector.check_host_has_enough_resources(conn, needed_cpus):
            print("Step [6] (Post-compression): Host now has enough resources.")
            new_vcpu_count = current_vcpu + needed_cpus
            print(f"Step [6]: Scaling up '{vm_name}' to {new_vcpu_count} vCPUs...")
            success = scaler.adjust_vcpu(host_ip, target_domain.UUIDString(), new_vcpu_count)
            return {"status": "success" if success else "error", "action": "scaled_up_after_compression"}
        else:
            return {"status": "failed", "message": "Failed to free up enough resources by compressing other VMs."}

    finally:
        if conn:
            conn.close()


def _find_compressible_vms(conn: libvirt.virConnect, target_vm_name: str, target_priority: int):
    """找到所有比目标VM优先级低的、非空闲的、可压缩的VM"""
    compressible_vms = []
    all_domains = conn.listAllDomains()
    for domain in all_domains:
        if not domain.isActive() or domain.name() == target_vm_name:
            continue

        policy = kvm_inspector.get_vm_policy_from_metadata(domain)
        priority = policy.get('priority', 99)
        usage = monitoring_agent.get_vm_resource_usage(domain)  # 复用我们的监控agent

        # 优先级更低，且CPU使用率低于缩容阈值（即“空闲”）
        if priority > target_priority and usage and usage['memory_usage_percent'] < policy.get('cpu_threshold_low', 20):
            compressible_vms.append(domain)

    # 按优先级从高到低排序（即优先压缩优先级最低的）
    compressible_vms.sort(key=lambda d: kvm_inspector.get_vm_policy_from_metadata(d).get('priority', 99), reverse=True)
    return compressible_vms


def _compress_vm(host_ip: str, domain: libvirt.virDomain) -> int:
    """压缩单个VM，返回释放的CPU数量"""
    policy = kvm_inspector.get_vm_policy_from_metadata(domain)
    current_vcpu = domain.info()[3]
    min_vcpu = policy.get('min_vcpu', 1)
    scale_step = policy.get('scale_step_cpu', 1)

    if current_vcpu > min_vcpu:
        new_vcpu_count = max(current_vcpu - scale_step, min_vcpu)
        print(f"Compressing VM '{domain.name()}' from {current_vcpu} to {new_vcpu_count} vCPUs...")
        success = kvm_scaler.adjust_vcpu(host_ip, domain.UUIDString(), new_vcpu_count)
        if success:
            return current_vcpu - new_vcpu_count
    return 0