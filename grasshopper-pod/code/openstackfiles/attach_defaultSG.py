from openstackfiles.openstack_client import OpenStackClient
from kubernetes import client, config


def attach_defaultSG():
    config.load_kube_config()
    v1 = client.CoreV1Api()
    node_list = v1.list_node()

    all_nodes = [node.metadata.name for node in node_list.items]
    insgs = OpenStackClient().neutron.list_security_groups()["security_groups"]
    already_created_sgs = [sg_items["name"] for sg_items in insgs]

    default_SG_name = "default"
    if default_SG_name in already_created_sgs:
        for node_name in all_nodes:
            instance = OpenStackClient().nova.servers.find(name=node_name)
            try:
                instance.add_security_group("default")
            except Exception as e:
                print(
                    f"Failed to attach security group 'default' to node {node_name}: {e}"
                )


if __name__ == "__main__":
    attach_defaultSG()
