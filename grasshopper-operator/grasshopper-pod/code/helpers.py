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


def traffic_pols(traffic: Traffic, n: Node, m: Node) -> Policy | None:
    for pol in ClusterState().get_policies():
        if running(pol.sel, n) and any(
            [
                pol.allow[0] == (labelset, traffic) and running(labelset, m)
                for labelset in ClusterState().get_label_sets()
            ]
        ):
            return pol
