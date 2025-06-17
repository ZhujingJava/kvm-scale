# handlers/alert_handler.py

from flask import Blueprint, jsonify, request

alert_bp = Blueprint('alert', __name__)


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
