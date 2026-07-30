from openstack_client import OpenStackClient


def detach_sg_starting_with_sg_dash():
    nova = OpenStackClient().get_nova()
    neutron = OpenStackClient().get_neutron()

    sgs_to_delete = set()

    print("=== Fetching all instances ===")
    servers = nova.servers.list()

    for server in servers:
        print(f"Checking server: {server.name} ({server.id})")

        # Get all ports attached to this instance
        ports = neutron.list_ports(device_id=server.id).get("ports", [])

        for port in ports:
            port_id = port["id"]
            attached_sgs = port.get("security_groups", [])

            new_sgs = []
            changed = False

            for sg_id in attached_sgs:
                sg = neutron.show_security_group(sg_id)["security_group"]
                sg_name = sg["name"]

                if sg_name.startswith("SG-"):
                    print(f" Detaching security group '{sg_name}' from port {port_id}")
                    changed = True
                    sgs_to_delete.add(sg_id)
                else:
                    new_sgs.append(sg_id)

            if changed:
                neutron.update_port(port_id, {"port": {"security_groups": new_sgs}})

    # Delete all the security groups
    print("=== Deleting security groups ===")
    for sg_id in sgs_to_delete:
        sg = neutron.show_security_group(sg_id)["security_group"]
        sg_name = sg["name"]
        try:
            print(f"Deleting security group: {sg_name} ({sg_id})")
            neutron.delete_security_group(sg_id)
        except Exception as e:
            print(f"Failed to delete {sg_name}: {e}")

def delete_all_sg_dash_groups():
    neutron = OpenStackClient().get_neutron()
    all_sgs = neutron.list_security_groups().get("security_groups", [])

    for sg in all_sgs:
        sg_id = sg["id"]
        sg_name = sg["name"]
        if sg_name.startswith("SG-"):
            try:
                print(f"Deleting security group: {sg_name} ({sg_id})")
                neutron.delete_security_group(sg_id)
            except Exception as e:
                print(f"Failed to delete {sg_name}: {e}")



if __name__ == "__main__":
    detach_sg_starting_with_sg_dash()
    delete_all_sg_dash_groups()
