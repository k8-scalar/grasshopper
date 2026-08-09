"""
Verifies the namespace-isolation fix (GitHub issue #8) still holds on this
branch: a NetworkPolicy's selector never matches a pod in a different
namespace just because the labels coincide, namespaceSelector peers (plain,
and combined with podSelector) work correctly, and conflicting()/redundant()
policy checks are namespace-aware too. Also covers two bugs found alongside
it: SecurityGroupModulePNS.SG_remove_conn no longer TypeErrors on
traffic_pols()'s single Policy|None return value, and the TestPolicies
fixtures classify the same way they did when the fix first landed.

Run with: python verify_namespace_isolation.py
"""
import glob
import os

import _bootstrap
from _bootstrap import check, report_and_exit, REPO_ROOT

from classes import LabelSet, Node, Pod, Policy, Traffic, INGRESS, CIDR, SecurityGroup, Rule
from cluster_state import ClusterState
from helpers import matching
from watchdog import WatchDog
from operator_code.watcher_operator import Watcher
from security_group_module import SecurityGroupModulePNS
import unittest.mock as mock


def reset_cluster_state():
    """ClusterState's containers are class-level and shared globally - clear
    them between scenarios so state doesn't leak."""
    ClusterState.map.clear()
    ClusterState.nodes.clear()
    ClusterState.pods.clear()
    ClusterState.policies.clear()
    ClusterState.security_groups.clear()
    ClusterState.namespaces.clear()
    ClusterState.offenders.clear()


def make_watchdog(pns=False):
    wd = WatchDog(PNS_scenario=pns)
    wd.matcher = mock.MagicMock()  # neutralize OpenStack-touching calls
    return wd


def pod_dict(name, namespace, labels, node_name):
    return {
        "metadata": {"name": name, "namespace": namespace, "labels": labels},
        "spec": {"nodeName": node_name},
    }


def policy_dict(name, namespace, sel_labels, allow_entries, port=80, protocol="TCP"):
    return {
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "podSelector": {"matchLabels": sel_labels},
            "ingress": [
                {"from": allow_entries, "ports": [{"port": port, "protocol": protocol}]}
            ],
        },
    }


# ============================================================
# Scenario A: issue #8 repro - same label, different namespaces
# ============================================================
print("\n=== Scenario A: issue #8 repro ===")
reset_cluster_state()
wd = make_watchdog(pns=False)

pol = Watcher.create_policy_from_policy_dict(
    policy_dict("ts-policy", "test", {"app": "teastore"}, [{"podSelector": {"matchLabels": {"app": "client"}}}])
)
pod_a = Watcher.create_pod_from_pod_dict(pod_dict("pod-a", "test", {"app": "teastore"}, "node1"))
pod_b = Watcher.create_pod_from_pod_dict(pod_dict("pod-b", "default", {"app": "teastore"}, "node2"))

ClusterState.add_node(Node("node1"))
ClusterState.add_node(Node("node2"))
ClusterState.add_namespace("test", {"kubernetes.io/metadata.name": "test"})
ClusterState.add_namespace("default", {"kubernetes.io/metadata.name": "default"})

wd.handle_new_policy(pol)
wd.handle_new_pod(pod_a)
wd.handle_new_pod(pod_b)

check("pod A (namespace=test) matches policy's sel", matching(pol.sel, pod_a) is True)
check("pod B (namespace=default) does NOT match policy's sel (the bug is fixed)", matching(pol.sel, pod_b) is False)


# ============================================================
# Scenario B: explicit namespaceSelector (custom namespace label)
# ============================================================
print("\n=== Scenario B: namespaceSelector on custom label ===")
reset_cluster_state()
wd = make_watchdog(pns=False)

pol_b = Watcher.create_policy_from_policy_dict(
    policy_dict(
        "ns-policy", "ns1", {"app": "server"},
        [{"namespaceSelector": {"matchLabels": {"environment": "production"}}}],
    )
)
ClusterState.add_namespace("ns1", {"kubernetes.io/metadata.name": "ns1"})
ClusterState.add_namespace("ns2", {"kubernetes.io/metadata.name": "ns2", "environment": "production"})
ClusterState.add_namespace("ns3", {"kubernetes.io/metadata.name": "ns3", "environment": "staging"})

pod_ns2 = Watcher.create_pod_from_pod_dict(pod_dict("pod-ns2", "ns2", {"any": "label"}, "node1"))
pod_ns3 = Watcher.create_pod_from_pod_dict(pod_dict("pod-ns3", "ns3", {"any": "label"}, "node2"))

peer_selector = pol_b.allow[0][0]
check("peer selector matches pod in ns2 (environment=production)", matching(peer_selector, pod_ns2) is True)
check("peer selector does NOT match pod in ns3 (environment=staging)", matching(peer_selector, pod_ns3) is False)


# ============================================================
# Scenario C: combined podSelector + namespaceSelector (AND semantics)
# ============================================================
print("\n=== Scenario C: combined podSelector + namespaceSelector ===")
reset_cluster_state()

pol_c = Watcher.create_policy_from_policy_dict(
    policy_dict(
        "combined-policy", "ns1", {"app": "server"},
        [{
            "podSelector": {"matchLabels": {"app": "client"}},
            "namespaceSelector": {"matchLabels": {"environment": "production"}},
        }],
    )
)
ClusterState.add_namespace("ns2", {"kubernetes.io/metadata.name": "ns2", "environment": "production"})
ClusterState.add_namespace("ns3", {"kubernetes.io/metadata.name": "ns3", "environment": "staging"})

peer_c = pol_c.allow[0][0]
pod_client_ns2 = Watcher.create_pod_from_pod_dict(pod_dict("p1", "ns2", {"app": "client"}, "n1"))
pod_client_ns3 = Watcher.create_pod_from_pod_dict(pod_dict("p2", "ns3", {"app": "client"}, "n1"))
pod_other_ns2 = Watcher.create_pod_from_pod_dict(pod_dict("p3", "ns2", {"app": "other"}, "n1"))

check("matches: right pod-label AND right namespace-label", matching(peer_c, pod_client_ns2) is True)
check("no match: right pod-label, wrong namespace-label", matching(peer_c, pod_client_ns3) is False)
check("no match: right namespace-label, wrong pod-label", matching(peer_c, pod_other_ns2) is False)


# ============================================================
# Scenario D: fixture regression - run real YAML fixtures through policy_check
# ============================================================
print("\n=== Scenario D: TestPolicies fixture regression ===")
try:
    import yaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False
    print("[SKIP] PyYAML not installed - skipping fixture regression scenario")

if HAVE_YAML:
    reset_cluster_state()

    fixture_root = os.path.join(REPO_ROOT, "tests", "TestPolicies")
    expected_offending = {
        "overly-permissive.yaml": True,
        "overly-permissive-cidr.yaml": True,
        "overly-permissive-any-namespace.yaml": True,
    }
    expected_non_offending = {
        "allow-app-1-app-2.yaml": False,
        "allow-app-2-app-1.yaml": False,
        "normal-policy.yaml": False,
        "allow-any-pod-in-namespace.yaml": False,
    }

    def load_policy(path):
        with open(path) as f:
            body = yaml.safe_load(f)
        return Watcher.create_policy_from_policy_dict(body)

    for fname, expected in expected_offending.items():
        matches = glob.glob(os.path.join(fixture_root, "**", fname), recursive=True)
        if not matches:
            print(f"[SKIP] fixture not found: {fname}")
            continue
        pol = load_policy(matches[0])
        for spol in WatchDog.split(pol):
            is_permissive = WatchDog.permissive(spol)
            check(f"{fname}: expected overly-permissive=True", is_permissive == expected)

    for fname, expected in expected_non_offending.items():
        matches = glob.glob(os.path.join(fixture_root, "**", fname), recursive=True)
        if not matches:
            print(f"[SKIP] fixture not found: {fname}")
            continue
        pol = load_policy(matches[0])
        for spol in WatchDog.split(pol):
            is_permissive = WatchDog.permissive(spol)
            check(f"{fname}: expected overly-permissive=False", is_permissive == expected)


# ============================================================
# Scenario E: SG_remove_conn / traffic_pols fix
# ============================================================
print("\n=== Scenario E: SecurityGroupModulePNS.SG_remove_conn no longer TypeErrors ===")
reset_cluster_state()

n1, n2 = Node("n1"), Node("n2")
ClusterState.add_node(n1)
ClusterState.add_node(n2)
ClusterState.add_namespace("default", {"kubernetes.io/metadata.name": "default"})

pol_e = Watcher.create_policy_from_policy_dict(
    policy_dict("pol-e", "default", {"app": "a"}, [{"podSelector": {"matchLabels": {"app": "b"}}}])
)
ClusterState.add_policy(pol_e)

sg_n1 = SecurityGroup(id="sg-n1", name="SG_n1")
sg_n2 = SecurityGroup(id="sg-n2", name="SG_n2")
ClusterState.add_security_group(sg_n1)
ClusterState.add_security_group(sg_n2)

# Simulate n1/n2 already running the relevant labelsets so traffic_pols finds pol_e.
ClusterState.add_pod(Watcher.create_pod_from_pod_dict(pod_dict("pa", "default", {"app": "a"}, "n1")))
ClusterState.add_pod(Watcher.create_pod_from_pod_dict(pod_dict("pb", "default", {"app": "b"}, "n2")))

try:
    SecurityGroupModulePNS.SG_remove_conn(pol_e, n1, n2)
    check("SG_remove_conn ran without TypeError", True)
except TypeError as e:
    check(f"SG_remove_conn ran without TypeError (got: {e})", False)


# ============================================================
# Scenario F: conflicting()/redundant() are namespace-aware too
# ============================================================
print("\n=== Scenario F: conflicting/redundant across namespaces ===")
reset_cluster_state()

# Two policies, identical labels, different namespaces - must NOT be seen as
# conflicting/redundant with each other (each is scoped to its own namespace).
pol_ns1 = Watcher.create_policy_from_policy_dict(
    policy_dict("dup-policy", "ns1", {"app": "web"}, [{"podSelector": {"matchLabels": {"app": "db"}}}])
)
pol_ns2 = Watcher.create_policy_from_policy_dict(
    policy_dict("dup-policy", "ns2", {"app": "web"}, [{"podSelector": {"matchLabels": {"app": "db"}}}])
)
spol_ns1 = WatchDog.split(pol_ns1)[0]
spol_ns2 = WatchDog.split(pol_ns2)[0]

check(
    "identical-label policies in different namespaces are not redundant",
    WatchDog.redundant(spol_ns2, [spol_ns1]) is False,
)
check(
    "identical-label policies in different namespaces are not conflicting",
    WatchDog.conflicting(spol_ns2, [spol_ns1]) is False,
)

# Same namespace, identical labels -> IS redundant (sanity check the positive case still works).
pol_ns1_dup = Watcher.create_policy_from_policy_dict(
    policy_dict("dup-policy-2", "ns1", {"app": "web"}, [{"podSelector": {"matchLabels": {"app": "db"}}}])
)
spol_ns1_dup = WatchDog.split(pol_ns1_dup)[0]
check(
    "identical-label policies in the SAME namespace ARE redundant",
    WatchDog.redundant(spol_ns1_dup, [spol_ns1]) is True,
)


report_and_exit()
