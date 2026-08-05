"""
Verifies that a NetworkPolicy with a CIDR/ipBlock peer doesn't crash the
locking/logging helpers that assume every involved labelset is a LabelSet.
Regression test for the bug found live: an ipBlock-based ingress rule (e.g.
allowing Typha access from 0.0.0.0/0) crashed handle_new_policy/
handle_removed_policy with "'CIDR' object has no attribute 'get_string_repr'"
in cluster_state.get_labelsets_string() and locking.lockmanager2.LockManager.

Run with: python verify_cidr_policy_locking.py
"""
import _bootstrap
from _bootstrap import check, report_and_exit

from classes import LabelSet, CIDR, Policy, Traffic
from cluster_state import ClusterState
from locking.lockmanager2 import LockManager

sel = LabelSet({"k8s-app": "calico-typha"}, namespace_labels={})
cidr_peer = CIDR("0.0.0.0/0")
traffic = Traffic(direction="ingress", port=5473, protocol="tcp")
pol = Policy(name="allow-typha-ingress-from-felix", sel=sel, allow=[(cidr_peer, traffic)], namespace="calico-system")

# get_involved_labelsets() / get_labelsets_string() must not crash and must drop the CIDR.
involved = pol.get_involved_labelsets()
check("get_involved_labelsets() excludes the CIDR peer", involved == [sel])

try:
    s = ClusterState.get_labelsets_string(set(involved) | {cidr_peer})
    check("get_labelsets_string() handles a CIDR entry without raising", "CIDR" in s or True)
except AttributeError as e:
    check(f"get_labelsets_string() handles a CIDR entry without raising ({e})", False)

# lock_labelsets() must not crash even if a CIDR sneaks into the list directly.
try:
    with LockManager().lock_labelsets([sel, cidr_peer]):
        pass
    check("lock_labelsets() handles a CIDR entry without raising", True)
except AttributeError as e:
    check(f"lock_labelsets() handles a CIDR entry without raising ({e})", False)

# Policy.get_string_repr() must not crash either.
try:
    pol.get_string_repr()
    check("Policy.get_string_repr() handles a CIDR allow-peer without raising", True)
except AttributeError as e:
    check(f"Policy.get_string_repr() handles a CIDR allow-peer without raising ({e})", False)

report_and_exit()
