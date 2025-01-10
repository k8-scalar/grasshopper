from classes import CIDR, Node, Policy, Rule, SecurityGroup
from cluster_state import ClusterState
from helpers import traffic_pols
from openstackfiles.openstack_client import OpenStackClient


# A class to encompass all functionality of actually manipulating the SG's
# through the Openstack API.
class SecurityGroupModule:
    @staticmethod
    def SGn(n: Node) -> SecurityGroup:
        return ClusterState().get_security_groups().get("SG_" + n.name)

    @staticmethod
    def add_rule_to_remotes(SG: SecurityGroup, rule: Rule) -> None:
        print(
            f"SGMod: Adding rule to {SG.name}, remote {rule.target.name}, port {rule.traffic.port}, type {rule.traffic.direction}"
        )
        neutron = OpenStackClient().get_neutron()
        created_rule = neutron.create_security_group_rule(
            {
                "security_group_rule": {
                    "direction": rule.traffic.direction,
                    "ethertype": "IPv4",
                    "protocol": rule.traffic.protocol,
                    "port_range_min": rule.traffic.port,
                    "port_range_max": rule.traffic.port,
                    "remote_group_id": rule.target.id,
                    "security_group_id": SG.id,
                }
            }
        )
        rule.id = created_rule["security_group_rule"]["id"]
        SG.remotes.add(rule)

    @staticmethod
    def remove_rule_from_remotes(SG: SecurityGroup, rule: Rule) -> None:
        if rule.id is None:
            existing_rules = SG.remotes
            for r in existing_rules:
                if r.target == rule.target and r.traffic == rule.traffic:
                    rule.id = r.id
                    break
            if rule.id is None:
                print(f"SGMod: {rule} not found in {SG.name}")
                print("Existing rules are:")
                for rule in SG.remotes:
                    print(rule)
                return
        print(f"SGMod: Removing rule {rule.id} from {SG.name}")
        neutron = OpenStackClient().get_neutron()
        neutron.delete_security_group_rule(security_group_rule=rule.id)
        # Create a new set without the rule to remove
        SG.remotes = {r for r in SG.remotes if r.id != rule.id}

    @staticmethod
    def SG_add_conn(pol: Policy, n: Node, m: Node) -> None:
        print(f"SGMod: Adding connection from {n.name} to {m.name}")
        rule: Rule = SecurityGroupModule.rule_from(pol, m)
        if rule not in SecurityGroupModule.SGn(n).remotes:
            SecurityGroupModule.add_rule_to_remotes(SecurityGroupModule.SGn(n), rule)

    @staticmethod
    def SG_remove_conn(pol: Policy, n: Node, m: Node) -> None:
        print(f"SGMod: Removing connection from {n.name} to {m.name}")
        if not isinstance(pol.allow[0][0], CIDR):
            if traffic_pols(pol.allow[0][1], n, m) != pol:
                print(
                    f"SGMod: policy has no running traffic from node {n.name} to node {m.name}"
                )
                return
            SecurityGroupModule.remove_rule_from_remotes(
                SecurityGroupModule.SGn(n), SecurityGroupModule.rule_from(pol, m)
            )
            print(f"SGMod: removed rule from {SecurityGroupModule.SGn(n).name}")

    @staticmethod
    def rule_from(pol: Policy, m: Node) -> Rule:
        A, traffic = pol.allow[0]
        return Rule(A if isinstance(A, CIDR) else SecurityGroupModule.SGn(m), traffic)
