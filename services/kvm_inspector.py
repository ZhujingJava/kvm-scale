# services/kvm_inspector.py

import libvirt
import yaml
from xml.etree import ElementTree as ET


# 加载配置
with open("config.yaml", "r") as f:
    CONFIG = yaml.safe_load(f)


def connect_libvirt(host_ip):
    """
    建立 libvirt 连接
    """
    server = CONFIG['servers'].get(host_ip)
    if not server:
        raise Exception(f"No config found for host {host_ip}")

    uri = server['libvirt_uri']
    conn = libvirt.open(uri)
    if not conn:
        raise Exception(f"Failed to open connection to {host_ip}")
    return conn


def has_qemu_agent(domain):
    """
    判断虚拟机是否配置了 QEMU Guest Agent
    """
    xml_desc = domain.XMLDesc(0)
    root = ET.fromstring(xml_desc)
    for channel in root.findall(".//devices/channel"):
        target = channel.find("target")
        if target is not None and 'name' in target.attrib:
            if target.attrib['name'] == 'org.qemu.guest_agent.0':
                return True
    return False


def is_elastic_vcpu(domain):
    """
    判断是否支持弹性 vCPU（是否设置 currentMemory < maxMemory）
    """
    xml_desc = domain.XMLDesc(0)
    root = ET.fromstring(xml_desc)
    vcpu = root.find("vcpu")
    if vcpu is not None and 'current' in vcpu.attrib:
        current = int(vcpu.attrib['current'])
        max_vcpu = int(vcpu.text)
        return current < max_vcpu
    return False

def get_vcpu_info(domain):
    """
    获取虚拟机的 vCPU 配置信息
    返回: {
        'max_vcpu': int,
        'curr_vcpu': int,
        'vcpu_mode': 'static' or 'elastic'
    }
    """
    xml_desc = domain.XMLDesc(0)
    root = ET.fromstring(xml_desc)

    vcpu_elem = root.find("vcpu")
    if vcpu_elem is None:
        raise ValueError("XML 中未找到 vCPU 配置")

    max_vcpu = int(vcpu_elem.text)  # 总共支持的最大 vCPU 数量
    curr_vcpu = int(vcpu_elem.get('current', max_vcpu))  # 当前使用数量，默认等于 max

    is_elastic = curr_vcpu < max_vcpu

    return {
        'max_vcpu': max_vcpu,
        'curr_vcpu': curr_vcpu,
        'vcpu_mode': 'elastic' if is_elastic else 'static'
    }

def is_elastic_memory(domain):
    """
    判断是否启用弹性内存（是否设置 currentMemory < maxMemory）
    """
    xml_desc = domain.XMLDesc(0)
    root = ET.fromstring(xml_desc)
    mem = root.find("memory")
    current_mem = root.find("currentMemory")

    if mem is not None and current_mem is not None:
        max_mem_kb = int(mem.text)
        curr_mem_kb = int(current_mem.text)
        return curr_mem_kb < max_mem_kb
    return False
def get_all_vms_info(host_ip):
    """
    获取指定物理服务器上的所有 KVM 虚拟机信息，并增强显示
    """
    conn = connect_libvirt(host_ip)
    vms = []

    try:
        domains = conn.listAllDomains(0)
        for domain in domains:
            dom_info = domain.info()

            # 解析 XML 获取更多信息
            xml_desc = domain.XMLDesc(0)
            root = ET.fromstring(xml_desc)

            # 提取内存信息
            mem_elem = root.find("memory")
            curr_mem_elem = root.find("currentMemory")
            max_mem_kb = int(mem_elem.text) if mem_elem is not None else 0
            curr_mem_kb = int(curr_mem_elem.text) if curr_mem_elem is not None else max_mem_kb

            # 获取 vCPU 信息
            vcpu_info = get_vcpu_info(domain)

            vms.append({
                'name': domain.name(),
                'uuid': domain.UUIDString(),
                'state': dom_info[0],  # 状态码
                'max_mem_gb': round(max_mem_kb / 1024 / 1024, 2),
                'curr_mem_gb': round(curr_mem_kb / 1024 / 1024, 2),
                'nr_virt_cpu': dom_info[3],  # CPU 数量（来自 info）
                # 'cpu_time_ms': dom_info[4] // 1_000_000,

                # vCPU 信息
                'max_vcpu': vcpu_info['max_vcpu'],
                'curr_vcpu': vcpu_info['curr_vcpu'],
                'vcpu_mode': vcpu_info['vcpu_mode'],

                'has_qemu_ga': has_qemu_agent(domain),
                'elastic_vcpu': vcpu_info['vcpu_mode'] == 'elastic',
                'elastic_memory': is_elastic_memory(domain),
            })
        return vms
    finally:
        conn.close()


def get_vm_policy_from_metadata(domain):
    """
    从虚拟机的 XML 元数据中解析伸缩策略。
    :param domain: libvirt domain object
    :return: 一个包含策略的字典, e.g., {'priority': 3, 'policy': 'elastic'}
    """
    try:
        # 获取完整的 XML 定义
        xml_desc = domain.XMLDesc(0)
        root = ET.fromstring(xml_desc)

        # 定义我们的命名空间
        ns = {'scale': 'http://kvm-scale.local/scale'}

        metadata = root.find('metadata')
        if metadata is None:
            return {}  # 没有 metadata 标签

        priority_tag = metadata.find('scale:priority', ns)
        policy_tag = metadata.find('scale:policy', ns)

        policy = {}
        if priority_tag is not None and priority_tag.text.isdigit():
            policy['priority'] = int(priority_tag.text)

        if policy_tag is not None:
            policy['policy'] = policy_tag.text

        return policy

    except Exception as e:
        print(f"解析虚拟机 {domain.name()} 的元数据失败: {e}")
        return {}