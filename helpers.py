from classes import LabelSet, Node, Pod, Policy, Traffic
from cluster_state import ClusterState


def running(L: LabelSet, n: Node):
    """
    True if a Pod with label set L is running on Node n
    """
    for pod in ClusterState().get_pods_by_node(n):
        if matching(L, pod):
            return True
    return False


def matching(L: LabelSet, p: Pod):
    """
    True if Pod p matches a label set L that has a record in the hash map,
    i.e., there is a policy which has a select or allow set that is a subset of L.
    """
    return L.issubset(p.label_set)


def traffic_pols(traffic: Traffic, n: Node, m: Node) -> list[Policy]:
    policies = list()
    pols = ClusterState().get_policies()
    for pol in pols:
        is_running_on_n = running(pol.sel, n)
        any_labelset = False
        for labelset in ClusterState().get_label_sets():
            if pol.allow[0] == (labelset, traffic) and running(labelset, m):
                any_labelset = True
                break

        if is_running_on_n and any_labelset:
            policies.append(pol)
    return policies
