from kubernetes import client, config

from openstackfiles.openstack_client import OpenStackClient
from openstackfiles.security_group_operations import (
    attach_security_group_to_instance,
    create_security_group_if_not_exists,
)
import logging

logger = logging.getLogger(__name__)

def initialize_cluster_configuration():
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
        config.load_incluster_config()
    else:
        config.load_kube_config()

def get_k8s_nodes():
    config.load_kube_config()
    v1 = client.CoreV1Api()

    try:
        nodes_list = v1.list_node().items
        return nodes_list
    except Exception as e:
        logging.info("Error while retrieving nodes:", e)
        return []


def create_sg_per_node(delete_existing_rules=False):
    nodes = get_k8s_nodes()
    if nodes:
        neutron = OpenStackClient().get_neutron()
        logging.info("Checking if per Node SGs are already created and attached")
        for node in nodes:
            node_name = node.metadata.name
            sg_name = "SG_" + node_name
            sg_description = "Security Group for " + node_name
            logging.info(f"checking node {node_name}")
            security_group = create_security_group_if_not_exists(
                sg_name, sg_description
            )

            if delete_existing_rules:
                for r in security_group["security_group_rules"]:
                    neutron.delete_security_group_rule(security_group_rule=r["id"])
            attach_security_group_to_instance(node_name, security_group)
        logging.info("Finished checking SGs")
    else:
        logging.info("No nodes found in the cluster.")


if __name__ == "__main__":
    create_sg_per_node(True)
