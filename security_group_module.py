from classes import CIDR, Node, Policy, Rule, SecurityGroup
from globals import security_groups
from credentials import neutron


# A class to encompass all functionality of actually manipulating the SG's
# through the Openstack API.
class SecurityGroupModule:
    def __init__(self):
        pass

    def SGn(n: Node) -> SecurityGroup:
        return security_groups.get("SG-" + n.name)

    def add_rule_to_remotes(SG: SecurityGroup, rule: Rule) -> None:
        rule = neutron.create_security_group_rule(
            {
                "security_group_rule": {
                    "direction": rule.traffic.direction,
                    "ethertype": "IPv4",
                    "protocol": rule.traffic.protocol,
                    "port_range_min": rule.traffic.port,
                    "port_range_max": rule.traffic.port,
                    "remote_ip_prefix": rule.target.cidr,
                    "security_group_id": rule.target.id,
                }
            }
        )
        rule.id = rule["security_group_rule"]["id"]
        SG.remotes.append(rule)

    def remove_rule_from_remotes(SG: SecurityGroup, rule: Rule) -> None:
        neutron.delete_security_group_rule(security_group_rule=rule.id)
        SG.remotes.remove(rule)

    def SG_add_conn(pol: Policy, n: Node, m: Node) -> None:
        rule: Rule = SecurityGroupModule.rule_from(pol, m)
        if rule not in SecurityGroupModule.SGn(n).remotes:
            SecurityGroupModule.add_rule_to_remotes(SecurityGroupModule.SGn(n), rule)

    def SG_remove_conn(pol: Policy, n: Node, m: Node) -> None:
        if not isinstance(pol.allow, CIDR):
            if SecurityGroupModule.traffic_pols(pol.allow, n, m) != pol:
                return
            SecurityGroupModule.remove_rule_from_remotes(
                SecurityGroupModule.SGn(n), SecurityGroupModule.rule_from(pol, m)
            )
