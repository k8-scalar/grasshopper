from classes import CIDR, LabelSet, Node, Policy, Rule, SecurityGroup, Traffic
from globals import policies, security_groups


# A class to encompass all functionality of actually manipulating the SG's
# through the Openstack API.
class SecurityGroupModule:
    def __init__(self):
        pass

    def SGn(n: Node) -> SecurityGroup:
        return security_groups.get("SG-" + n.name)

    def add_rule_to_remotes(SG: SecurityGroup, rule: Rule) -> None:
        # TODO: use openstack to add rule
        SG.remotes.append(rule)

    def remove_rule_from_remotes(SG: SecurityGroup, rule: Rule) -> None:
        # TODO: use openstack to remove rule
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
