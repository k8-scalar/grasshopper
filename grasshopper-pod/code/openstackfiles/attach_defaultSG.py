import os
from kubernetes import client, config
from classes import node_project_from_labels
from openstackfiles.openstack_client import OpenStackClient


def initialize_cluster_configuration():
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
        config.load_incluster_config()
    else:
        config.load_kube_config()


def attach_defaultSG():
    """
    (Re-)attaches the "default" SG to every worker node. This is the
    mirror image of detach_defaultSG() and exists for the same reason
    setup_gh() needs it as its first step: a worker only has workerSG's
    static rules until Grasshopper is deployed and has actually processed
    whatever NetworkPolicies (e.g. the Typha ipBlock policy) open the
    dynamic, per-node rules real traffic needs - "default" is what covers
    that gap. If a previous Grasshopper deployment already ran
    detach_defaultSG() on this cluster, a fresh bootstrap run needs to put
    "default" back first, rather than assume it's still there. Nodes can
    belong to different OpenStack projects - "default" (and the worker
    instance itself) only exist within their own project, so this is
    resolved and acted on per-project, one OpenStackClient per project,
    same as detach_defaultSG()/create_master_and_workerSG().
    """
    # Load Kubernetes configuration
    initialize_cluster_configuration()

    # Initialize the Kubernetes API client
    v1 = client.CoreV1Api()
    node_list = v1.list_node()

    # Master node label
    master_node_label = "node-role.kubernetes.io/control-plane"

    workers_by_project = {}
    for node in node_list.items:
        labels = node.metadata.labels or {}
        if master_node_label in labels:
            continue
        project = node_project_from_labels(labels)
        workers_by_project.setdefault(project, []).append(node.metadata.name)

    default_SG_name = "default"
    for project, worker_names in workers_by_project.items():
        neutron = OpenStackClient.for_project(project).get_neutron()
        nova = OpenStackClient.for_project(project).get_nova()

        existing_security_groups = neutron.list_security_groups()["security_groups"]
        already_created_sgs = [sg["name"] for sg in existing_security_groups]

        if default_SG_name not in already_created_sgs:
            continue

        for node_name in worker_names:
            # Find the instance by node name and (re-)attach the security group
            instance = nova.servers.find(name=node_name)
            try:
                instance.add_security_group(default_SG_name)
            except Exception:
                pass


if __name__ == "__main__":
    attach_defaultSG()
