from kubernetes import client, config
from openstackfiles.openstack_client import OpenStackClient
from openstackfiles.security_group_operations import (
    add_rules_to_security_group,
    attach_security_group_to_instance,
    create_security_group_if_not_exists,
)

# Master node label
master_node_label = "node-role.kubernetes.io/control-plane"

# Security group names
MASTER_SG_NAME = "masterSG"
WORKER_SG_NAME = "workerSG"

# Security group rules for masterSG and workerSG
MASTER_SG_RULES = [
    # Egress rules for masterSG
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": 22,
        "port_range_max": 22,
        "remote_group_id": None,
        "remote_ip_prefix": "0.0.0.0/0",
    },  # SSH to all
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": 443,
        "port_range_max": 443,
        "remote_ip_prefix": "0.0.0.0/0",
    },  # HTTPS to any
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": 9053,
        "port_range_max": 9053,
        "remote_group_id": None,
        "remote_ip_prefix": "0.0.0.0/0",
    },  # DNS TCP to all
    {
        "direction": "egress",
        "protocol": "udp",
        "port_range_min": 53,
        "port_range_max": 53,
        "remote_group_id": None,
        "remote_ip_prefix": "0.0.0.0/0",
    },  #  DNS UDP to all
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": 10250,
        "port_range_max": 10250,
        "remote_group_id": None,
        "remote_ip_prefix": None,
    },  # Kubelet API to workerSG
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": 10259,
        "port_range_max": 10259,
        "remote_group_id": None,
        "remote_ip_prefix": None,
    },  # Cluster management to workerSG
    # Ingress rules for masterSG
    {
        "direction": "ingress",
        "protocol": "tcp",
        "port_range_min": 22,
        "port_range_max": 22,
        "remote_ip_prefix": "0.0.0.0/0",
    },  # SSH from any
    {
        "direction": "ingress",
        "protocol": "tcp",
        "port_range_min": 53,
        "port_range_max": 53,
        "remote_group_id": None,
    },  # DNS TCP from workerSG
    {
        "direction": "ingress",
        "protocol": "tcp",
        "port_range_min": 443,
        "port_range_max": 443,
        "remote_group_id": None,
    },  # HTTPS from workerSG
    {
        "direction": "ingress",
        "protocol": "udp",
        "port_range_min": 53,
        "port_range_max": 53,
        "remote_group_id": None,
    },  # DNS UDP from workerSG
    {
        "direction": "ingress",
        "protocol": "tcp",
        "port_range_min": 2379,
        "port_range_max": 2379,
        "remote_group_id": None,
    },  # etcd from workerSG
    {
        "direction": "ingress",
        "protocol": "tcp",
        "port_range_min": 10250,
        "port_range_max": 10250,
        "remote_group_id": None,
    },  # Kubelet API from workerSG
    {
        "direction": "ingress",
        "protocol": "tcp",
        "port_range_min": 10259,
        "port_range_max": 10259,
        "remote_group_id": None,
    },  # Cluster management from workerSG
    {
        "direction": "ingress",
        "protocol": "tcp",
        "port_range_min": 6443,
        "port_range_max": 6443,
        "remote_group_id": None,
    },  # Kubernetes API server from workerSG
    {
        "direction": "ingress",
        "protocol": "tcp",
        "port_range_min": 179,
        "port_range_max": 179,
        "remote_group_id": None,
    },  # BGP protocol from workerSG
]

WORKER_SG_RULES = [
    # Egress rules for workerSG
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": 22,
        "port_range_max": 22,
        "remote_group_id": None,
    },  # SSH to masterSG
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": 53,
        "port_range_max": 53,
        "remote_group_id": None,
    },  # DNS to masterSG
    {
        "direction": "egress",
        "protocol": "udp",
        "port_range_min": 53,
        "port_range_max": 53,
        "remote_group_id": None,
    },  # DNS to masterSG
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": 9053,
        "port_range_max": 9053,
        "remote_group_id": None,
        "remote_ip_prefix": "0.0.0.0/0",
    },  # DNS TCP to all
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": 443,
        "port_range_max": 443,
        "remote_group_id": None,
    },  # HTTPS to masterSG
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": 2379,
        "port_range_max": 2379,
        "remote_group_id": None,
    },  # etcd to masterSG
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": 6443,
        "port_range_max": 6443,
        "remote_group_id": None,
    },  # API server to masterSG
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": 10250,
        "port_range_max": 10250,
        "remote_group_id": None,
    },  # Kubelet API to masterSG
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": 10259,
        "port_range_max": 10259,
        "remote_group_id": None,
    },  # Cluster management to masterSG
    {
        "direction": "egress",
        "protocol": "tcp",
        "port_range_min": 179,
        "port_range_max": 179,
        "remote_group_id": None,
    },  # BGP protocol to masterSG
    # Ingress rules for workerSG
    {
        "direction": "ingress",
        "protocol": "tcp",
        "port_range_min": 22,
        "port_range_max": 22,
        "remote_group_id": None,
    },  # SSH from masterSG
    {
        "direction": "ingress",
        "protocol": "tcp",
        "port_range_min": 10250,
        "port_range_max": 10250,
        "remote_group_id": None,
    },  # Kubelet API from masterSG
    {
        "direction": "ingress",
        "protocol": "tcp",
        "port_range_min": 10259,
        "port_range_max": 10259,
        "remote_group_id": None,
    },  # Cluster management from masterSG
    {
        "direction": "ingress",
        "protocol": "udp",
        "port_range_min": 53,
        "port_range_max": 53,
        "remote_group_id": None,
    },  # DNS UDP from workerSG
]


# Function to create a security group if it doesn't exist


# Function to retrieve the Nova instance ID from Kubernetes node information
def get_instance_id_from_k8s_node(k8s_node):
    # Just return the name of the Kubernetes node
    return k8s_node.metadata.name


def create_master_and_workerSG():
    # Kubernetes client configuration
    config.load_kube_config()
    v1 = client.CoreV1Api()

    # Create or get security groups
    master_sg_id = create_security_group_if_not_exists(
        MASTER_SG_NAME, "Master security group"
    )
    worker_sg_id = create_security_group_if_not_exists(
        WORKER_SG_NAME, "Worker security group"
    )

    # Add rules to security groups
    add_rules_to_security_group(master_sg_id, MASTER_SG_RULES, worker_sg_id)
    add_rules_to_security_group(worker_sg_id, WORKER_SG_RULES, master_sg_id)

    # Retrieve the Kubernetes node list
    node_list = v1.list_node()

    # Loop over all Kubernetes nodes
    for node in node_list.items:
        instance_id = get_instance_id_from_k8s_node(node)
        if instance_id:
            # Check if the node is a control-plane node
            if master_node_label in node.metadata.labels:
                print(
                    f"Attaching {MASTER_SG_NAME} to control-plane node: {node.metadata.name}"
                )
                attach_security_group_to_instance(instance_id, MASTER_SG_NAME)
            else:
                print(
                    f"Attaching {WORKER_SG_NAME} to worker node: {node.metadata.name}"
                )
                attach_security_group_to_instance(instance_id, WORKER_SG_NAME)
        else:
            print(f"Could not determine instance ID for node: {node.metadata.name}")

    print(
        "Security groups successfully created, rules added, and attached to Kubernetes nodes."
    )
