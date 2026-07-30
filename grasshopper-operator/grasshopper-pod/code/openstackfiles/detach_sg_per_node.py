from openstackfiles.openstack_client import OpenStackClient


def remove_security_groups_by_name(node_name_prefix):
    nova = OpenStackClient().get_nova()
    neutron = OpenStackClient().get_neutron()

    instances = nova.servers.list()
    for instance in instances:
        for sg in instance.security_groups:
            if sg["name"].startswith(node_name_prefix):
                print(f"detaching and deleting {sg['name']}")
                nova.servers.remove_security_group(instance.id, sg["name"])
                security_groups = neutron.list_security_groups(name=sg["name"])
                for group in security_groups["security_groups"]:
                    if group["name"] == sg["name"]:
                        security_group_id = group["id"]
                        neutron.delete_security_group(security_group_id)


if __name__ == "__main__":
    node_name_prefix = "SG_"
    remove_security_groups_by_name(node_name_prefix)
