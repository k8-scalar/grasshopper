from kubernetes import client, config
from classes import node_project_from_labels
from openstackfiles.openstack_client import OpenStackClient


def detach_defaultSG():
    """
    Detaches the "default" SG from every worker node so it stops permitting
    the wide-open traffic OpenStack attaches it with by default, and
    Grasshopper's own SGs become the actual enforcement. Nodes can belong to
    different OpenStack projects - "default" (and the worker instance itself)
    only exist within their own project, so this has to be resolved and acted
    on per-project, one OpenStackClient per project, same as
    create_master_and_workerSG().
    """
    # Load Kubernetes configuration
    config.load_kube_config()

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
            # Find the instance by node name and detach the security group
            instance = nova.servers.find(name=node_name)
            try:
                instance.remove_security_group(default_SG_name)
            except:
                pass


if __name__ == "__main__":
    detach_defaultSG()
