from kubernetes import client, config
from openstackfiles.openstack_client import OpenStackClient


def detach_defaultSG():
    # Load Kubernetes configuration
    config.load_kube_config()

    # Initialize the Kubernetes API client
    v1 = client.CoreV1Api()
    node_list = v1.list_node()

    neutron = OpenStackClient().get_neutron()
    nova = OpenStackClient().get_nova()

    # Master node label
    master_node_label = "node-role.kubernetes.io/control-plane"

    all_nodes = [(node.metadata.name, node.metadata.labels) for node in node_list.items]

    # Retrieve existing security groups
    existing_security_groups = neutron.list_security_groups()["security_groups"]
    already_created_sgs = [sg["name"] for sg in existing_security_groups]

    default_SG_name = "default"
    if default_SG_name in already_created_sgs:
        for node_name, labels in all_nodes:
            # Skip nodes with the master label
            if master_node_label in labels:
                continue

            # Find the instance by node name and detach the security group
            instance = nova.servers.find(name=node_name)
            try:
                instance.remove_security_group(default_SG_name)
            except:
                pass


if __name__ == "__main__":
    detach_defaultSG()
