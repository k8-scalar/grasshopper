from classes import CIDR, MapEntry, Policy
from cluster_state import ClusterState


def add_policy(pol: Policy) -> None:
    mapping = ClusterState().get_map()
    if pol.sel not in ClusterState().get_map():
        mapping[pol.sel] = MapEntry()
    mapping[pol.sel].select_pols.append(pol)
    if not isinstance(pol.allow, CIDR):
        if pol.allow not in mapping:
            mapping[pol.allow] = MapEntry()
        mapping[pol.allow].allow_pols.append(pol)


def remove_policy(pol: Policy) -> None:
    mapping = ClusterState().get_map()
    s = mapping[pol.sel]
    a = mapping[pol.allow]
    s.select_pols.remove(pol)
    if not s.select_pols and not s.allow_pols:
        del mapping[pol.sel]
    a.allow_pols.remove(pol)
    if not a.select_pols and not a.allow_pols:
        del mapping[pol.allow]
