"""
Verifies the fix for WatchDog.conflicting()/redundant() never actually
comparing CIDR-typed allow-rule content - they only ever handled LabelSet
peers (skipping any CIDR-typed one via an `isinstance` guard), so two
CIDR-typed policies sharing a selector were declared conflicting/redundant
purely from the selector match, regardless of whether their CIDRs actually
overlapped.

This is not hypothetical: a real NetworkPolicy with N>1 separate ipBlock
peers under one selector expands into N separate (CIDR, traffic) allow-rules
(Watcher.create_allow_list_ingress), and WatchDog.split() turns each into its
own single-allow-rule sub-policy, all sharing that same selector - so the
second sub-policy onward was flagged "redundant" against the first and the
WHOLE parent policy got silently rejected into ClusterState.offenders, with
zero SG rule ever created for any of its peers. Reproduced live: a 39-/32-
peer Typha ingress policy was rejected outright on every restart. See
Deployment/networkpolicies/typha-ingress.yaml's git history for the incident
and the (temporary, single-CIDR) workaround this fix makes unnecessary.

Covers:
- helpers.cidr_issubset(): the actual containment semantics (equal, narrower-
  within-wider, disjoint, different IP versions).
- WatchDog._peer_issubset(): dispatches to cidr_issubset for two CIDRs,
  selector_issubset for two LabelSets, and never confuses a LabelSet with a
  CIDR.
- WatchDog.redundant()/conflicting()/policy_check() at the level the real
  incident lived at: a multi-peer CIDR policy (disjoint /32s under one
  selector) must NOT be rejected - this is the actual regression test for
  the live incident. A genuinely redundant narrower-CIDR policy (already
  fully covered by an existing wider one, same selector) must still be
  correctly rejected - confirming the fix adds real containment checking,
  not just "never reject CIDR policies".

Run with: python verify_cidr_redundancy_check.py
"""
import os

import _bootstrap
from _bootstrap import check, report_and_exit

from classes import CIDR, LabelSet, Policy, Traffic, INGRESS
from cluster_state import ClusterState
from watchdog import WatchDog
from helpers import cidr_issubset
from openstackfiles.openstack_client import OpenStackClient

os.environ["OS_AUTH_URL"] = "https://example.com:5000"
os.environ["OS_APPLICATION_CREDENTIAL_ID"] = "id"
os.environ["OS_APPLICATION_CREDENTIAL_SECRET"] = "secret"


def reset_all():
    ClusterState.map.clear()
    ClusterState.nodes.clear()
    ClusterState._nodes_by_name.clear()
    ClusterState.pods.clear()
    ClusterState.policies.clear()
    ClusterState.security_groups.clear()
    ClusterState.namespaces.clear()
    ClusterState.offenders.clear()
    OpenStackClient._instances.clear()
    OpenStackClient._credentials_by_key = None


TYPHA_SEL = LabelSet({"k8s-app": "calico-typha"}, namespace_labels=None)
TCP_5473 = Traffic(INGRESS, 5473, "TCP")


def cidr_policy(name, peers: list[str]) -> Policy:
    """A Policy with one allow-rule per CIDR peer, same shape split() would
    later break it into - mirrors what Watcher.create_policy_from_policy_dict
    actually builds for a NetworkPolicy with N ipBlock peers in one rule."""
    return Policy(name, TYPHA_SEL, [(CIDR(c), TCP_5473) for c in peers], "calico-system")


# ============================================================
# Scenario A: cidr_issubset() itself - the containment primitive.
# ============================================================
print("=== Scenario A: cidr_issubset() containment semantics ===")
check("a network is a subset of itself",
      cidr_issubset(CIDR("172.22.0.0/16"), CIDR("172.22.0.0/16")))
check("a /24 is a subset of the /16 that contains it",
      cidr_issubset(CIDR("172.22.0.0/16"), CIDR("172.22.8.0/24")))
check("the /16 is NOT a subset of the narrower /24 it contains",
      not cidr_issubset(CIDR("172.22.8.0/24"), CIDR("172.22.0.0/16")))
check("two disjoint /32s are not subsets of each other",
      not cidr_issubset(CIDR("10.0.0.1/32"), CIDR("10.0.0.2/32")))
check("different IP versions are never comparable",
      not cidr_issubset(CIDR("172.22.0.0/16"), CIDR("::1/128")))
check("a malformed CIDR string does not raise, just returns False",
      not cidr_issubset(CIDR("not-a-cidr"), CIDR("172.22.0.0/16")))


# ============================================================
# Scenario B: WatchDog._peer_issubset() dispatch - never confuses a LabelSet
# with a CIDR, but correctly delegates when both sides match.
# ============================================================
print("\n=== Scenario B: _peer_issubset() type dispatch ===")
ls_broad = LabelSet({}, namespace_labels=None)
ls_narrow = LabelSet({"app": "x"}, namespace_labels=None)
check("two LabelSets still dispatch to selector_issubset (unchanged behavior)",
      WatchDog._peer_issubset(ls_broad, ls_narrow))
check("a LabelSet and a CIDR are never comparable",
      not WatchDog._peer_issubset(ls_broad, CIDR("172.22.0.0/16")))
check("a CIDR and a LabelSet are never comparable (order swapped)",
      not WatchDog._peer_issubset(CIDR("172.22.0.0/16"), ls_broad))
check("two CIDRs dispatch to cidr_issubset",
      WatchDog._peer_issubset(CIDR("172.22.0.0/16"), CIDR("172.22.8.0/24")))


# ============================================================
# Scenario C: the actual live incident - a policy with multiple DISJOINT
# CIDR peers under one selector must not self-collide. Before the fix,
# WatchDog.split()'s second sub-policy onward was flagged "redundant"
# against the first purely because they share a selector - regardless of
# their (genuinely non-overlapping) CIDR content.
# ============================================================
print("\n=== Scenario C: multi-peer CIDR policy does not self-collide (the live incident) ===")
reset_all()
wd = WatchDog(PNS_scenario=True)

typha_policy = cidr_policy("grasshopper-typha-ingress", [
    "172.22.14.30/32", "172.22.14.53/32", "172.22.14.18/32",
])

check("policy_check accepts a multi-peer CIDR policy with disjoint peers",
      WatchDog.policy_check(typha_policy))

wd.handle_new_policy(typha_policy)
check("policy was tracked in ClusterState, not rejected to offenders",
      len(ClusterState.get_offenders()) == 0)
check("all 3 disjoint-peer split sub-policies ended up in ClusterState.get_policies()",
      len(ClusterState.get_policies()) == 3)


# ============================================================
# Scenario D: genuine redundancy must still be caught - a narrower CIDR,
# same selector and traffic, fully covered by an existing wider one.
# ============================================================
print("\n=== Scenario D: a genuinely redundant narrower CIDR is still rejected ===")
reset_all()
wd = WatchDog(PNS_scenario=True)

wide_policy = cidr_policy("allow-wide", ["172.22.0.0/16"])
wd.handle_new_policy(wide_policy)
check("the wide /16 policy was accepted", len(ClusterState.get_offenders()) == 0)

narrow_policy = cidr_policy("allow-narrow-redundant", ["172.22.8.0/24"])
check("policy_check correctly rejects a /24 already fully covered by the passed /16",
      not WatchDog.policy_check(narrow_policy))

wd.handle_new_policy(narrow_policy)
check("the redundant narrower policy landed in offenders, not ClusterState",
      narrow_policy in ClusterState.get_offenders())


# ============================================================
# Scenario E: a DIFFERENT (non-overlapping) CIDR under the same selector as
# an already-passed one must NOT be rejected - proving the fix distinguishes
# genuine redundancy from a mere selector match.
# ============================================================
print("\n=== Scenario E: a disjoint CIDR under the same selector is accepted ===")
reset_all()
wd = WatchDog(PNS_scenario=True)

first_policy = cidr_policy("allow-first", ["10.0.0.0/24"])
wd.handle_new_policy(first_policy)
check("the first policy was accepted", len(ClusterState.get_offenders()) == 0)

second_policy = cidr_policy("allow-second-disjoint", ["10.0.1.0/24"])
check("policy_check accepts a disjoint CIDR sharing the same selector",
      WatchDog.policy_check(second_policy))

wd.handle_new_policy(second_policy)
check("the disjoint second policy was tracked, not rejected to offenders",
      second_policy not in ClusterState.get_offenders())


report_and_exit()
