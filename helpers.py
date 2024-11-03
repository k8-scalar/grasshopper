from classes import CIDR, LabelSet, Node, Pod, Policy, Rule, Traffic
from globals import policies, security_groups
from security_group_module import SecurityGroupModule


def running(L: LabelSet, n: Node):
    # True if a Pod with label set L is running on Node n
    pass


def matching(L: LabelSet, p: Pod):
    # True if Pod p matches a label set L that has a record in the hash map, i.e., there is a policy which has a select or allow set that is a subset of L
    pass


def traffic_pols(traffic: Traffic, n: Node, m: Node) -> Policy | None:
    for pol in policies:
        if running(pol.sel, n) and any(
            [pol.allow == (sg, traffic) and running(sg, m) for sg in security_groups]
        ):
            return pol


def rule_from(pol: Policy, m: Node) -> Rule:
    A, traffic = pol.allow
    return Rule(A if isinstance(A, CIDR) else SecurityGroupModule.SGn(m), traffic)
