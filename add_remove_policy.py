from classes import CIDR, MapEntry, Policy
from globals import Map


def add_policy(pol: Policy) -> None:
    if pol.sel not in Map:
        Map[pol.sel] = MapEntry()
    Map[pol.sel].select_pols.append(pol)
    if not isinstance(pol.allow, CIDR):
        if pol.allow not in Map:
            Map[pol.allow] = MapEntry()
        Map[pol.allow].allow_pols.append(pol)


def remove_policy(pol: Policy) -> None:
    s = Map[pol.sel]
    a = Map[pol.allow]
    s.select_pols.remove(pol)
    if not s.select_pols and not s.allow_pols:
        del Map[pol.sel]
    a.allow_pols.remove(pol)
    if not a.select_pols and not a.allow_pols:
        del Map[pol.allow]
