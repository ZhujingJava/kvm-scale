from services.kvm_adjuster import adjust_kvm_resources
from utils.queue_manager import add_to_queue, process_queue

def process_alert(alert):
    instance_ip = alert['labels'].get('instance', '').split(':')[0]
    severity = alert['labels'].get('severity', 'warning')
    priority = 1 if severity == 'critical' else 2
    add_to_queue((instance_ip, alert), priority)
    process_queue()
