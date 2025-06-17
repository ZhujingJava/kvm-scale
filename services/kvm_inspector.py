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
    try:
        xml_desc = domain.XMLDesc(0)
        root = ET.fromstring(xml_desc)
        for channel in root.findall(".//devices/channel"):
            target = channel.find("target")
            if target is not None and 'name' in target.attrib:
                if target.attrib['name'] == 'org.qemu.guest_agent.0':
                    return True
    except ET.ParseError as pe:
        print(f"[ERROR] XML parse failed (has_qemu_agent): {pe}")
    except Exception as e:
        print(f"[ERROR] Failed to check QEMU GA for {domain.name()}: {e}")
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
    try:
        xml_desc = domain.XMLDesc(0)
        root = ET.fromstring(xml_desc)

        vcpu_elem = root.find("vcpu")
        if vcpu_elem is None:
            raise ValueError("XML 中未找到 vCPU 配置")

        max_vcpu = int(vcpu_elem.text)
        curr_vcpu = int(vcpu_elem.get('current', max_vcpu))
        is_elastic = curr_vcpu < max_vcpu

        return {
            'max_vcpu': max_vcpu,
            'curr_vcpu': curr_vcpu,
            'vcpu_mode': 'elastic' if is_elastic else 'static'
        }

    except ET.ParseError as pe:
        print(f"[ERROR] XML parse failed (get_vcpu_info): {pe}")
    except Exception as e:
        print(f"[ERROR] Failed to get vCPU info for {domain.name()}: {e}")
    return {
        'max_vcpu': 0,
        'curr_vcpu': 0,
        'vcpu_mode': 'static'
    }


def is_elastic_memory(domain):
    """
    判断是否启用弹性内存（是否设置 currentMemory < maxMemory）
    """
    try:
        xml_desc = domain.XMLDesc(0)
        root = ET.fromstring(xml_desc)

        mem_elem = root.find("memory")
        curr_mem_elem = root.find("currentMemory")

        if mem_elem is not None and curr_mem_elem is not None:
            max_mem_kb = int(mem_elem.text)
            curr_mem_kb = int(curr_mem_elem.text)
            return curr_mem_kb < max_mem_kb
    except ET.ParseError as pe:
        print(f"[ERROR] XML parse failed (is_elastic_memory): {pe}")
    except Exception as e:
        print(f"[ERROR] Failed to check elastic memory for {domain.name()}: {e}")
    return False


def get_domain_cpu_usage(domain):
    """
    获取虚拟机 CPU 使用率（需要 QEMU GA）
    """
    try:
        if not domain.isActive():  # 👈 先判断是否运行中
            return 0.0
        stats = domain.getCPUStats(True)
        if stats and 'cpu_time' in stats[0]:
            return round(stats[0]['cpu_time'] / 10_000_000, 2)  # ns -> %
    except Exception as e:
        print(f"[WARN] Failed to get CPU usage for {domain.name()}: {e}")
    return 0.0



def get_domain_memory_usage(domain):
    """
    获取虚拟机内存使用率（需要 QEMU GA）
    """
    try:
        if not domain.isActive():  # 👈 先判断是否运行中
            return 0.0
        stats = domain.memoryStats()
        if stats:
            return round((stats['actual'] - stats['available']) * 100.0 / stats['actual'], 2)
    except Exception as e:
        print(f"[WARN] Failed to get memory usage for {domain.name()}: {e}")
    return 0.0


def get_all_vms_info(host_ip):
    """
    获取指定 KVM 主机上的所有虚拟机及其详细信息（含弹性、QEMU GA、资源使用等）
    """
    conn = connect_libvirt(host_ip)
    vms = []

    try:
        domains = conn.listAllDomains(0)
        for domain in domains:
            try:
                info = domain.info()
                xml_desc = domain.XMLDesc(0)
                root = ET.fromstring(xml_desc)

                # 提取内存信息
                mem_elem = root.find("memory")
                curr_mem_elem = root.find("currentMemory")
                max_mem_kb = int(mem_elem.text) if mem_elem is not None else 0
                curr_mem_kb = int(curr_mem_elem.text) if curr_mem_elem is not None else max_mem_kb

                # 获取 vCPU 信息
                vcpu_info = get_vcpu_info(domain)

                # 获取 QEMU GA 状态
                qemu_ga = has_qemu_agent(domain)

                # 构建返回对象
                elastic_vcpu = vcpu_info['curr_vcpu'] < vcpu_info['max_vcpu']
                elastic_memory = curr_mem_kb < max_mem_kb
                cpu_usage = get_domain_cpu_usage(domain) if info[0] == libvirt.VIR_DOMAIN_RUNNING else 0.0
                mem_usage = get_domain_memory_usage(domain) if info[0] == libvirt.VIR_DOMAIN_RUNNING else 0.0

                ip_address = ""
                if qemu_ga:
                    # 如果 QEMU GA 存在，尝试获取 eth0 的 IP 地址
                    try:
                        if domain.isActive():
                            # 获取虚拟机的接口信息
                            interfaces = domain.interfaceAddresses(libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_AGENT, 0)
                            # 优先查找 eth0 接口
                            if 'eth0' in interfaces:
                                value = interfaces['eth0']
                                if 'addrs' in value:
                                    for addr in value['addrs']:
                                        # 只获取 IPv4 地址
                                        if addr['type'] == libvirt.VIR_IP_ADDR_TYPE_IPV4:
                                            ip_address = addr['addr']
                                            break
                            else:
                                # 如果没有 eth0，回退到第一个有地址的接口
                                for key, value in interfaces.items():
                                    if 'addrs' in value:
                                        for addr in value['addrs']:
                                            if addr['type'] == libvirt.VIR_IP_ADDR_TYPE_IPV4:
                                                ip_address = addr['addr']
                                                break
                                        if ip_address:
                                            break
                    except Exception as e:
                        print(f"[WARN] Failed to get IP address for {domain.name()}: {e}")
                vms.append({
                    "name": domain.name(),
                    "uuid": domain.UUIDString(),
                    "state": "running" if info[0] == libvirt.VIR_DOMAIN_RUNNING else "shutdown",
                    "curr_mem_kb": curr_mem_kb,
                    "max_mem_kb": max_mem_kb,
                    "curr_mem_gb": round(curr_mem_kb / 1024 / 1024, 2),
                    "max_mem_gb": round(max_mem_kb / 1024 / 1024, 2),
                    "curr_vcpu": vcpu_info['curr_vcpu'],
                    "max_vcpu": vcpu_info['max_vcpu'],
                    "vcpu_mode": 'elastic' if elastic_vcpu else 'static',
                    "has_qemu_ga": qemu_ga,
                    "elastic_vcpu": elastic_vcpu,
                    "elastic_memory": elastic_memory,
                    "cpu_usage_percent": cpu_usage,
                    "mem_usage_percent": mem_usage,
                    "ip_address": ip_address  # 添加IP地址字段
                })

            except ET.ParseError as pe:
                print(f"[ERROR] XML Parse failed for {domain.name()}: {pe}")
                continue
            except Exception as e:
                print(f"[ERROR] Failed to collect data for {domain.name()}: {e}")
                continue

    finally:
        conn.close()

    return vms


def get_all_vms_on_host(host_ip):
    """
    兼容旧接口：获取指定 KVM 主机上的所有虚拟机信息。
    """
    return get_all_vms_info(host_ip)
