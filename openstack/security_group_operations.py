from openstack.openstack_client import OpenStackClient


def create_security_group_if_not_exists(sg_name, description):
    neutron = OpenStackClient.get_neutron()

    existing_sgs = neutron.list_security_groups(name=sg_name)
    if existing_sgs["security_groups"]:
        print(f"Security group '{sg_name}' already exists.")
        return existing_sgs["security_groups"][0]["id"]

    print(f"Creating security group: {sg_name}")
    sg = neutron.create_security_group(
        {"security_group": {"name": sg_name, "description": description}}
    )
    return sg["security_group"]["id"]


def add_rules_to_security_group(sg_id, rules, remote_sg_id):
    neutron = OpenStackClient.get_neutron()

    existing_rules = neutron.list_security_group_rules(security_group_id=sg_id)[
        "security_group_rules"
    ]

    for rule in rules:
        # Check if rule already exists
        if not any(
            r["direction"] == rule["direction"]
            and r["protocol"] == rule["protocol"]
            and r.get("port_range_min") == rule.get("port_range_min")
            and r.get("port_range_max") == rule.get("port_range_max")
            and r.get("remote_ip_prefix") == rule.get("remote_ip_prefix")
            for r in existing_rules
        ):

            # Add rule if it doesn't exist
            neutron.create_security_group_rule(
                {
                    "security_group_rule": {
                        "security_group_id": sg_id,
                        "direction": rule["direction"],
                        "protocol": rule["protocol"],
                        "port_range_min": rule.get("port_range_min"),
                        "port_range_max": rule.get("port_range_max"),
                        "remote_ip_prefix": rule.get("remote_ip_prefix"),
                        "remote_group_id": (
                            rule.get("remote_group_id")
                            if rule.get("remote_ip_prefix")
                            else remote_sg_id
                        ),
                        "ethertype": "IPv4",
                    }
                }
            )
            print(
                f"Added {rule['direction']} rule for {rule['protocol']} on ports {rule.get('port_range_min')} - {rule.get('port_range_max')} to security group {sg_id}"
            )


def attach_security_group_to_instance(instance_id, security_group_name):
    nova = OpenStackClient.get_nova()

    server = nova.servers.find(name=instance_id)
    security_groups = server.list_security_group()

    # Check if security group is already attached
    if any(sg.name == security_group_name for sg in security_groups):
        print(
            f"Security group {security_group_name} already attached to instance {instance_id}"
        )
        return

    print(f"Attaching security group {security_group_name} to instance {instance_id}")
    server.add_security_group(security_group_name)
