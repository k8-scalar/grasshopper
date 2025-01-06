from kubernetes import client, config

from openstackfiles.openstack_client import OpenStackClient
from openstackfiles.security_group_operations import (
    attach_security_group_to_instance,
    create_security_group_if_not_exists,
)


def get_k8s_nodes():
    config.load_kube_config()
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
        neutron = OpenStackClient().get_neutron()
        print("Checking if per Node SGs are already created and attached")
        for node in nodes:
            node_name = node.metadata.name
            sg_name = "SG_" + node_name
            sg_description = "Security Group for " + node_name
            print(f"checking node {node_name}")
            security_group = create_security_group_if_not_exists(
                sg_name, sg_description
            )

            if delete_existing_rules:
                for r in security_group["security_group_rules"]:
                    neutron.delete_security_group_rule(security_group_rule=r["id"])
            attach_security_group_to_instance(node_name, security_group)
        print("Finished checking SGs")
    else:
        print("No nodes found in the cluster.")


if __name__ == "__main__":
    create_sg_per_node(True)
