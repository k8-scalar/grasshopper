import os
from kubernetes import client, config

from classes import node_project_from_labels, node_internal_ip_from_addresses
from cluster_state import ClusterState
from openstackfiles.openstack_client import OpenStackClient
from openstackfiles.security_group_operations import (
    attach_security_group_to_instance,
    create_security_group_if_not_exists,
)

def initialize_cluster_configuration():
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
        config.load_incluster_config()
    else:
        config.load_kube_config()

def get_k8s_nodes():
    initialize_cluster_configuration()
    v1 = client.CoreV1Api()

    try:
        nodes_list = v1.list_node().items
        return nodes_list
    except Exception as e:
        print("Error while retrieving nodes:", e)
        return []


def create_sg_per_node(delete_existing_rules=False):
    nodes = get_k8s_nodes()
    if nodes:
        print("Checking if per Node SGs are already created and attached")
        for node in nodes:
            node_name = node.metadata.name
            node_project = node_project_from_labels(node.metadata.labels)
            node_ip = node_internal_ip_from_addresses(node.status.addresses)
            sg_name = "SG_" + node_name
            sg_description = "Security Group for " + node_name
            print(f"checking node {node_name} (project={node_project}, ip={node_ip})")

            neutron = OpenStackClient.for_project(node_project).get_neutron()
            security_group = create_security_group_if_not_exists(
                sg_name, sg_description, project_key=node_project
            )

            if delete_existing_rules:
                for r in security_group["security_group_rules"]:
                    neutron.delete_security_group_rule(security_group_rule=r["id"])
            attach_security_group_to_instance(node_name, security_group, project_key=node_project)

            # Keep the ClusterState Node record's project/internal_ip in sync too,
            # in case this ran after cluster_state.py's own node population (both
            # read the same label/address, this just guards against ordering).
            existing = ClusterState.get_node(node_name)
            if existing:
                existing.project = node_project
                existing.internal_ip = node_ip
        print("Finished checking SGs")
    else:
        print("No nodes found in the cluster.")


if __name__ == "__main__":
    create_sg_per_node(True)
