import os
from kubernetes import client, config
from classes import node_project_from_labels, node_internal_ip_from_addresses
from openstackfiles.openstack_client import OpenStackClient
from openstackfiles.security_group_operations import (
    add_rules_to_security_group,
    add_cidr_rules_to_security_group,
    attach_security_group_to_instance,
    create_security_group_if_not_exists,
)


def initialize_cluster_configuration():
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
        config.load_incluster_config()
    else:
        config.load_kube_config()


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
    """
    Creates masterSG/workerSG and wires up the control-plane <-> worker
    connectivity every k8s cluster needs (API server, kubelet, etcd, BGP, DNS).

    Nodes can belong to different OpenStack projects (multi-domain). Neutron
    does not allow attaching a security group to an instance in a different
    project, nor referencing a remote_group_id across projects - so:
      - masterSG/workerSG are created and attached PER PROJECT (only in
        projects that actually have a matching node).
      - Same-project master<->worker rules keep using remote_group_id,
        unchanged from the single-project case.
      - Cross-project master<->worker rules use CIDR of each individual peer
        node's real IP instead (control-plane services listen on the node's
        own network stack, not a Calico pod overlay, so no VXLAN/encapsulation
        concern applies here - this is a plain node-to-node CIDR rule).
    """
    # Kubernetes client configuration
    initialize_cluster_configuration()
    v1 = client.CoreV1Api()
    node_list = v1.list_node().items

    # Group nodes by (project, role).
    masters_by_project = {}
    workers_by_project = {}
    for node in node_list:
        instance_id = get_instance_id_from_k8s_node(node)
        if not instance_id:
            print(f"Could not determine instance ID for node: {node.metadata.name}")
            continue
        project = node_project_from_labels(node.metadata.labels)
        ip = node_internal_ip_from_addresses(node.status.addresses)
        entry = (instance_id, ip)
        if master_node_label in (node.metadata.labels or {}):
            masters_by_project.setdefault(project, []).append(entry)
        else:
            workers_by_project.setdefault(project, []).append(entry)

    # Create masterSG/workerSG in every project that actually has a matching
    # node, and attach each node to its OWN project's SG.
    master_sgs = {}
    worker_sgs = {}
    for project, masters in masters_by_project.items():
        master_sgs[project] = create_security_group_if_not_exists(
            MASTER_SG_NAME, "Master security group", project_key=project
        )
        for instance_id, _ in masters:
            print(f"Attaching {MASTER_SG_NAME} to control-plane node: {instance_id} (project {project})")
            attach_security_group_to_instance(instance_id, master_sgs[project], project_key=project)

    for project, workers in workers_by_project.items():
        worker_sgs[project] = create_security_group_if_not_exists(
            WORKER_SG_NAME, "Worker security group", project_key=project
        )
        for instance_id, _ in workers:
            print(f"Attaching {WORKER_SG_NAME} to worker node: {instance_id} (project {project})")
            attach_security_group_to_instance(instance_id, worker_sgs[project], project_key=project)

    # Wire up every master-project x worker-project pair that needs rules.
    for master_project, masters in masters_by_project.items():
        master_sg = master_sgs[master_project]
        for worker_project, workers in workers_by_project.items():
            worker_sg = worker_sgs[worker_project]
            if master_project == worker_project:
                add_rules_to_security_group(master_sg["id"], MASTER_SG_RULES, worker_sg["id"], project_key=master_project)
                add_rules_to_security_group(worker_sg["id"], WORKER_SG_RULES, master_sg["id"], project_key=worker_project)
            else:
                master_ips = [f"{ip}/32" for _, ip in masters if ip]
                worker_ips = [f"{ip}/32" for _, ip in workers if ip]
                add_cidr_rules_to_security_group(master_sg["id"], MASTER_SG_RULES, worker_ips, project_key=master_project)
                add_cidr_rules_to_security_group(worker_sg["id"], WORKER_SG_RULES, master_ips, project_key=worker_project)

    print(
        "Security groups successfully created, rules added, and attached to Kubernetes nodes."
    )
