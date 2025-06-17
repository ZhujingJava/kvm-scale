# handlers/host_map_api.py

from flask import Blueprint, request, jsonify
from services.vm_locator import KVMMAP_KEY, redis_client

host_map_bp = Blueprint('host_map', __name__)


@host_map_bp.route('/map/kvm', methods=['POST'])
def add_kvm_mapping():
    data = request.get_json()
    kvm_ip = data.get("kvm_ip")
    host_ip = data.get("host_ip")

    if not kvm_ip or not host_ip:
        return jsonify({"error": "Missing kvm_ip or host_ip"}), 400

    redis_client.hset(KVMMAP_KEY, kvm_ip, host_ip)
    return jsonify({
        "status": "success",
        "message": f"Mapped KVM {kvm_ip} to Host {host_ip}"
    })


@host_map_bp.route('/map/kvm/<kvm_ip>', methods=['DELETE'])
def remove_kvm_mapping(kvm_ip):
    result = redis_client.hdel(KVMMAP_KEY, kvm_ip)
    if result == 1:
        return jsonify({"status": "success", "message": f"Removed mapping for {kvm_ip}"})
    else:
        return jsonify({"status": "not_found", "message": f"No mapping found for {kvm_ip}"}), 404


@host_map_bp.route('/map/kvm', methods=['GET'])
def get_all_mappings():
    mappings = redis_client.hgetall(KVMMAP_KEY)
    return jsonify(mappings)
