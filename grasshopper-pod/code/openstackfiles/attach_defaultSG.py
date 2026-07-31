import os
from openstackfiles.openstack_client import OpenStackClient
from classes import node_project_from_labels
from kubernetes import client, config


def initialize_cluster_configuration():
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
        config.load_incluster_config()
    else:
        config.load_kube_config()


def attach_defaultSG():
    """
    Re-attaches the "default" SG to every node - the reverse of
    detach_defaultSG(). Nodes can belong to different OpenStack projects -
    "default" (and the instance itself) only exist within their own project,
    so this is resolved and acted on per-project, same as detach_defaultSG().
    """
    initialize_cluster_configuration()
    v1 = client.CoreV1Api()
    node_list = v1.list_node()

    nodes_by_project = {}
    for node in node_list.items:
        labels = node.metadata.labels or {}
        project = node_project_from_labels(labels)
        nodes_by_project.setdefault(project, []).append(node.metadata.name)

    default_SG_name = "default"
    for project, node_names in nodes_by_project.items():
        neutron = OpenStackClient.for_project(project).get_neutron()
        nova = OpenStackClient.for_project(project).get_nova()

        existing_security_groups = neutron.list_security_groups()["security_groups"]
        already_created_sgs = [sg["name"] for sg in existing_security_groups]

        if default_SG_name not in already_created_sgs:
            continue

        for node_name in node_names:
            instance = nova.servers.find(name=node_name)
            try:
                instance.add_security_group(default_SG_name)
            except Exception as e:
                print(
                    f"Failed to attach security group 'default' to node {node_name}: {e}"
                )


if __name__ == "__main__":
    attach_defaultSG()
