from openstackfiles.openstack_client import OpenStackClient, DEFAULT_PROJECT_KEY


def create_security_group_if_not_exists(sg_name, description, project_key=DEFAULT_PROJECT_KEY):
    neutron = OpenStackClient.for_project(project_key).get_neutron()

    existing_sgs = neutron.list_security_groups(name=sg_name)
    if existing_sgs["security_groups"]:
        print(f"Security group '{sg_name}' already exists.")
        return existing_sgs["security_groups"][0]

    print(f"Creating security group: {sg_name}")
    sg = neutron.create_security_group(
        {"security_group": {"name": sg_name, "description": description}}
    )
    return sg["security_group"]


def add_rules_to_security_group(sg_id, rules, remote_sg_id, project_key=DEFAULT_PROJECT_KEY):
    """
    Adds each rule to sg_id, using remote_sg_id (remote_group_id) for any rule
    that doesn't already specify its own fixed remote_ip_prefix. remote_sg_id
    must belong to the SAME OpenStack project as sg_id - Neutron does not allow
    a remote_group_id reference across projects (see
    add_cidr_rules_to_security_group for the cross-project equivalent).
    """
    neutron = OpenStackClient.for_project(project_key).get_neutron()

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


def add_cidr_rules_to_security_group(sg_id, rules, remote_cidrs, project_key=DEFAULT_PROJECT_KEY):
    """
    Cross-project equivalent of add_rules_to_security_group: for a peer that
    lives in a DIFFERENT OpenStack project (so remote_group_id is not legal),
    adds one CIDR-targeted rule per (rule, cidr) pair instead, for every rule
    that doesn't already specify its own fixed remote_ip_prefix (those "to/from
    anywhere" rules are added once, unchanged, exactly as
    add_rules_to_security_group does).
    """
    neutron = OpenStackClient.for_project(project_key).get_neutron()

    existing_rules = neutron.list_security_group_rules(security_group_id=sg_id)[
        "security_group_rules"
    ]

    def rule_exists(direction, protocol, port_min, port_max, remote_ip_prefix):
        return any(
            r["direction"] == direction
            and r["protocol"] == protocol
            and r.get("port_range_min") == port_min
            and r.get("port_range_max") == port_max
            and r.get("remote_ip_prefix") == remote_ip_prefix
            for r in existing_rules
        )

    def create(direction, protocol, port_min, port_max, remote_ip_prefix):
        neutron.create_security_group_rule(
            {
                "security_group_rule": {
                    "security_group_id": sg_id,
                    "direction": direction,
                    "protocol": protocol,
                    "port_range_min": port_min,
                    "port_range_max": port_max,
                    "remote_ip_prefix": remote_ip_prefix,
                    "ethertype": "IPv4",
                }
            }
        )
        print(f"Added {direction} rule for {protocol} on ports {port_min}-{port_max} to security group {sg_id}, remote {remote_ip_prefix}")

    for rule in rules:
        if rule.get("remote_ip_prefix"):
            if not rule_exists(rule["direction"], rule["protocol"], rule.get("port_range_min"), rule.get("port_range_max"), rule["remote_ip_prefix"]):
                create(rule["direction"], rule["protocol"], rule.get("port_range_min"), rule.get("port_range_max"), rule["remote_ip_prefix"])
            continue
        for cidr in remote_cidrs:
            if not rule_exists(rule["direction"], rule["protocol"], rule.get("port_range_min"), rule.get("port_range_max"), cidr):
                create(rule["direction"], rule["protocol"], rule.get("port_range_min"), rule.get("port_range_max"), cidr)


def attach_security_group_to_instance(instance_id, security_group, project_key=DEFAULT_PROJECT_KEY):
    nova = OpenStackClient.for_project(project_key).get_nova()

    server = nova.servers.find(name=instance_id)
    security_groups = server.list_security_group()
    security_group_name = security_group["name"]

    # Check if security group is already attached
    if any(sg.name == security_group_name for sg in security_groups):
        print(
            f"Security group {security_group_name} already attached to instance {instance_id}"
        )
        return

    print(f"Attaching security group {security_group_name} to instance {instance_id}")
    server.add_security_group(security_group_name)
