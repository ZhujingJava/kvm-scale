import heapq

priority_queue = []

def add_to_queue(item, priority):
    heapq.heappush(priority_queue, (priority, item))

def process_queue():
    while priority_queue:
        priority, item = heapq.heappop(priority_queue)
        instance_ip, alert = item
        # 示例：动态增加 CPU 和内存
        adjust_kvm_resources(instance_ip, cpu=4, memory="8G")
