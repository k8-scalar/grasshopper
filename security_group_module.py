from classes import CIDR, Node, Policy, Rule, SecurityGroup
from cluster_state import ClusterState
from openstackfiles.openstack_client import OpenStackClient


# A class to encompass all functionality of actually manipulating the SG's
# through the Openstack API.
class SecurityGroupModule:
    @staticmethod
    def SGn(n: Node) -> SecurityGroup:
        return ClusterState().get_security_groups().get("SG-" + n.name)

    @staticmethod
    def add_rule_to_remotes(SG: SecurityGroup, rule: Rule) -> None:
        print(f"Adding rule {rule.id} to {SG.name}")
        neutron = OpenStackClient().get_neutron()
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

    @staticmethod
    def remove_rule_from_remotes(SG: SecurityGroup, rule: Rule) -> None:
        print(f"Removing rule {rule.id} from {SG.name}")
        neutron = OpenStackClient().get_neutron()
        neutron.delete_security_group_rule(security_group_rule=rule.id)
        SG.remotes.remove(rule)

    @staticmethod
    def SG_add_conn(pol: Policy, n: Node, m: Node) -> None:
        print(f"Adding connection from {n.name} to {m.name}")
        rule: Rule = SecurityGroupModule.rule_from(pol, m)
        if rule not in SecurityGroupModule.SGn(n).remotes:
            SecurityGroupModule.add_rule_to_remotes(SecurityGroupModule.SGn(n), rule)

    @staticmethod
    def SG_remove_conn(pol: Policy, n: Node, m: Node) -> None:
        print(f"Removing connection from {n.name} to {m.name}")
        if not isinstance(pol.allow, CIDR):
            if SecurityGroupModule.traffic_pols(pol.allow, n, m) != pol:
                return
            SecurityGroupModule.remove_rule_from_remotes(
                SecurityGroupModule.SGn(n), SecurityGroupModule.rule_from(pol, m)
            )

    @staticmethod
    def rule_from(pol: Policy, m: Node) -> Rule:
        A, traffic = pol.allow
        return Rule(A if isinstance(A, CIDR) else SecurityGroupModule.SGn(m), traffic)
