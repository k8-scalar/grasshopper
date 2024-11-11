from kubelet_watch_server import master_port
from ostackfiles.create_master_and_workerSG import add_rules_to_security_group

MASTER_SG_RULES = [
    # Ingress rules for masterSG
    {
        "direction": "ingress",
        "protocol": "tcp",
        "port_range_min": master_port,
        "port_range_max": master_port,
        "remote_group_id": None,
    },  # RPC calls from workerSG
]

WORKER_SG_RULES = [
    # Egress rules for workerSG
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": master_port,
        "port_range_max": master_port,
        "remote_group_id": None,
    },  # RPC calls to masterSG
]


def add_rpc_rules_to_master_and_worker_sg(neutron, master_sg_id, worker_sg_id):
    add_rules_to_security_group(neutron, master_sg_id, MASTER_SG_RULES, worker_sg_id)
    add_rules_to_security_group(neutron, worker_sg_id, WORKER_SG_RULES, master_sg_id)
