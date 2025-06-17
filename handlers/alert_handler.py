# handlers/alert_handler.py

from flask import Blueprint, jsonify, request
from pip._internal.utils import logging

from services.scaler import scale_vm_cpu, scale_vm_memory
from services.kvm_inspector import get_all_vms_on_host
alert_bp = Blueprint('alert', __name__)

logger = logging.getLogger(__name__)
last_scale_time = {}  # 防止重复扩容的缓存 { "host_vm": timestamp }

MAX_CPU = 10
MAX_MEM_GB = 32
SCALE_COOLDOWN = 300  # 冷却时间，单位秒
def process_alert(alert_type, instance, severity, description):
    print(f"[ALERT] Type: {alert_type}, VM IP: {instance}, Severity: {severity}")

    if alert_type not in ["cpu", "memory"]:
        print("[INFO] Only CPU/Memory alerts are handled.")
        return

    # 步骤一：查找宿主机
    host_ip = find_host_by_vm_ip(instance)
    if not host_ip:
        print(f"[ERROR] Could not find host for VM {instance}")
        return

    print(f"[INFO] Found host: {host_ip} for VM {instance}")

    # 步骤二：获取该宿主机上的所有虚拟机
    try:
        vms = get_all_vms_on_host(host_ip)
        if not vms or len(vms) == 0:
            print(f"[INFO] No VMs found on host {host_ip}")
            return

        # 查找对应虚拟机
        target_vm = next((vm for vm in vms if vm.get("ip") == instance), None)
        if not target_vm:
            print(f"[INFO] No VM found with IP {instance} on host {host_ip}")
            return

        vm_name = target_vm["name"]
        vm_key = f"{host_ip}_{vm_name}"

        now = time.time()
        last_time = last_scale_time.get(vm_key, 0)
        if now - last_time < SCALE_COOLDOWN:
            print(f"[INFO] {vm_key} is cooling down. Skipping.")
            return

        print(f"[INFO] Found running VM: {vm_name}")

        if alert_type == "cpu":
            new_cpu = target_vm["curr_vcpu"] + 2
            if new_cpu > MAX_CPU:
                print(f"[WARN] Max CPU limit reached for {vm_name}")
                return

            success = scale_vm_cpu(vm_name, host_ip, new_cpu)
            if success:
                print(f"[SUCCESS] CPU scaled to {new_cpu} cores for {vm_name} on {host_ip}")
                last_scale_time[vm_key] = now
            else:
                print(f"[ERROR] Failed to scale CPU for {vm_name}")

        elif alert_type == "memory":
            new_mem = max(target_vm["curr_mem_gb"] + 2, int(target_vm["curr_mem_gb"] * 1.5))
            if new_mem > MAX_MEM_GB:
                print(f"[WARN] Max memory limit reached for {vm_name}")
                return

            success = scale_vm_memory(vm_name, host_ip, new_mem)
            if success:
                print(f"[SUCCESS] Memory scaled to {new_mem} GB for {vm_name} on {host_ip}")
                last_scale_time[vm_key] = now
            else:
                print(f"[ERROR] Failed to scale memory for {vm_name}")

    except Exception as e:
        print(f"[ERROR] Error during scaling: {str(e)}")

@alert_bp.route('/alerts', methods=['POST'])
def handle_prometheus_alert():
    data = request.json
    print("[INFO] Received alert:", data)

    if not data or 'status' not in data:
        return jsonify({"error": "Invalid alert format"}), 400

    # 提取关键字段
    labels = data.get("labels", {})
    annotations = data.get("annotations", {})

    alert_name = labels.get("alertname", "unknown")
    instance = labels.get("instance", "").split(":")[0]
    severity = labels.get("severity", "unknown")
    summary = annotations.get("summary", "")
    description = annotations.get("description", "")

    # 分类告警类型
    alert_type = classify_alert(alert_name, summary, description)

    # 执行后续动作（可扩展）
    process_alert(alert_type, instance, severity, description)

    return jsonify({
        "status": "received",
        "alert_type": alert_type,
        "instance": instance,
        "severity": severity
    })


def classify_alert(alert_name, summary, description):
    alert_name = alert_name.lower()
    summary = summary.lower()
    description = description.lower()

    if any(kw in alert_name for kw in ["cpu", "highcpuload"]) or \
       any(kw in summary for kw in ["cpu", "load"]) or \
       any(kw in description for kw in ["cpu", "load"]):
        return "cpu"

    elif any(kw in alert_name for kw in ["memory", "mem"]) or \
         any(kw in summary for kw in ["memory", "mem"]) or \
         any(kw in description for kw in ["memory", "mem"]):
        return "memory"

    elif any(kw in alert_name for kw in ["disk", "filesystem"]) or \
         any(kw in summary for kw in ["disk", "filesystem"]) or \
         any(kw in description for kw in ["disk", "filesystem"]):
        return "disk"

    else:
        return "unknown"


def process_alert(alert_type, instance, severity, description):
    print(f"[ALERT] Type: {alert_type}, Host: {instance}, Severity: {severity}")

    if alert_type == "cpu":
        print(f"[ACTION] CPU 高负载告警: {description}")
        # TODO: 这里可以调用扩容函数或发送通知

    elif alert_type == "memory":
        print(f"[ACTION] 内存高使用告警: {description}")
        # TODO: 检查是否支持弹性内存，决定是否扩容

    elif alert_type == "disk":
        print(f"[ACTION] 磁盘空间不足告警: {description}")
        # TODO: 清理缓存、扩展磁盘配额、通知用户

    else:
        print(f"[ACTION] 未知告警: {description}")
