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
    Also checks that p's actual namespace satisfies L's namespace scope (if any).
    """
    if not L.issubset(p.label_set):
        return False
    if L.namespace_labels is None:
        return True
    namespace_labels = ClusterState.get_namespace_labels(p.namespace)
    return all(
        key in namespace_labels and namespace_labels[key] == value
        for key, value in L.namespace_labels.items()
    )

def matching_ls(L: LabelSet, ls: LabelSet):
    """
    True if the Labelset L is a subset of ls.
    """
    return L.issubset(ls)


def selector_issubset(a: LabelSet, b: LabelSet):
    """
    True if selector a is broader-or-equal to selector b, across both the pod-label
    dimension and the namespace-scope dimension. Used to compare two selectors
    against each other (e.g. policy conflict/redundancy detection), as opposed to
    matching() which compares a selector against a live Pod.
    """
    return a.issubset(b) and a.namespace_issubset(b)


def traffic_pols(traffic: Traffic, n: Node, m: Node) -> Policy | None:
    for pol in ClusterState().get_policies():
        if running(pol.sel, n) and any(
            [
                pol.allow[0] == (labelset, traffic) and running(labelset, m)
                for labelset in ClusterState().get_label_sets()
            ]
        ):
            return pol
