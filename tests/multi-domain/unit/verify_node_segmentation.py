"""
Verifies the "basics" segmentation-aware enforcement described in
Nestor-paper/formalization/isolation.tex: pods on nodes in different,
isolated segments must not be able to talk to each other, even when a
NetworkPolicy would otherwise allow it - and no SG rule connecting such a
pair may ever be created. Covers, end to end:

- ClusterState.is_isolated(n, m) - the isolated(n,m) predicate itself.
- SG_add_conn blocking rule creation for an isolated pair, via the real
  WatchDog/policy/pod pipeline (not just a direct unit check).
- An unisolated pair (same segment, or segmentation off) still connects
  normally - this feature must not become a blanket lockdown.
- revoke_rules_for_isolated_pairs() tearing down an ALREADY-created rule when
  a segmentation update newly isolates that pair - the point being that
  isolation must be enforced retroactively, not just for future connections.
- main_operator.sync_node_segments_from_nsp() wiring all of the above
  together from a NodeSegmentationPolicy CR body, including the on.resume/
  on.field entrypoint itself.
- connectivity_configmap_data()'s key/value shape.

Run with: python verify_node_segmentation.py
"""
import unittest.mock as mock

import _bootstrap
from _bootstrap import check, report_and_exit

from classes import Node, SecurityGroup
from cluster_state import ClusterState
from watchdog import WatchDog
from openstackfiles.openstack_client import OpenStackClient
from operator_code.watcher_operator import Watcher
from security_group_module import SecurityGroupModulePNS

import os

os.environ["OS_AUTH_URL"] = "https://example.com:5000"
os.environ["OS_APPLICATION_CREDENTIAL_ID"] = "id"
os.environ["OS_APPLICATION_CREDENTIAL_SECRET"] = "secret"

with mock.patch("sys.argv", ["main_operator.py", "--mode", "PNS"]):
    import main_operator


def reset_all():
    ClusterState.map.clear()
    ClusterState.nodes.clear()
    ClusterState._nodes_by_name.clear()
    ClusterState.pods.clear()
    ClusterState.policies.clear()
    ClusterState.security_groups.clear()
    ClusterState.namespaces.clear()
    ClusterState.offenders.clear()
    ClusterState.clear_node_segments()
    OpenStackClient._instances.clear()
    OpenStackClient._credentials_by_key = None
    main_operator.MODE = "PNS"


def pod_dict(name, ns, labels, node):
    return {"metadata": {"name": name, "namespace": ns, "labels": labels}, "spec": {"nodeName": node}}


def pol_dict(name, ns, sel, allow, port=8080):
    return {
        "metadata": {"name": name, "namespace": ns},
        "spec": {"podSelector": {"matchLabels": sel}, "ingress": [{"from": allow, "ports": [{"port": port, "protocol": "TCP"}]}]},
    }


def remotes_of(sg_name):
    return ClusterState.get_security_group(sg_name).remotes


def setup_two_node_pair():
    """n-a/n-b, both same project, a policy allowing client-b -> server-a, one pod each."""
    ClusterState.add_node(Node("n-a", project="default", internal_ip="10.0.0.1"))
    ClusterState.add_node(Node("n-b", project="default", internal_ip="10.0.0.2"))
    ClusterState.add_security_group(SecurityGroup(id="sg-a", name="SG_n-a", project="default"))
    ClusterState.add_security_group(SecurityGroup(id="sg-b", name="SG_n-b", project="default"))
    wd = WatchDog(PNS_scenario=True)
    pol = Watcher.create_policy_from_policy_dict(pol_dict("allow-b-to-a", "ns1", {"app": "server-a"}, [{"podSelector": {"matchLabels": {"app": "client-b"}}}]))
    pod_a = Watcher.create_pod_from_pod_dict(pod_dict("pod-a", "ns1", {"app": "server-a"}, "n-a"))
    pod_b = Watcher.create_pod_from_pod_dict(pod_dict("pod-b", "ns1", {"app": "client-b"}, "n-b"))
    return wd, pol, pod_a, pod_b


# ============================================================
# Scenario A: isolated(n,m) predicate itself
# ============================================================
print("=== Scenario A: ClusterState.is_isolated() predicate ===")
reset_all()
check("no NSP seen yet -> nothing isolated", not ClusterState.is_isolated("n-a", "n-b"))

ClusterState.set_node_segments({"n-a": "seg-1", "n-b": "seg-2"}, isolated=True)
check("different segments, isolation on -> isolated", ClusterState.is_isolated("n-a", "n-b"))

ClusterState.set_node_segments({"n-a": "seg-1", "n-b": "seg-1"}, isolated=True)
check("same segment, isolation on -> NOT isolated", not ClusterState.is_isolated("n-a", "n-b"))

ClusterState.set_node_segments({"n-a": "seg-1"}, isolated=True)
check("n-b not assigned to any segment -> NOT isolated (not segmented, not blocked)", not ClusterState.is_isolated("n-a", "n-b"))

ClusterState.set_node_segments({"n-a": "seg-1", "n-b": "seg-2"}, isolated=False)
check("segments known but isolation off -> NOT isolated", not ClusterState.is_isolated("n-a", "n-b"))


# ============================================================
# Scenario B: SG_add_conn blocks a would-be-allowed connection between an
# isolated pair, via the real WatchDog/policy/pod pipeline - not just a
# direct rule_from()/is_isolated() check.
# ============================================================
print("\n=== Scenario B: isolated pair - NetworkPolicy allows it, segmentation blocks it ===")
reset_all()
wd, pol, pod_a, pod_b = setup_two_node_pair()
ClusterState.set_node_segments({"n-a": "seg-1", "n-b": "seg-2"}, isolated=True)

wd.handle_new_pod(pod_a)
wd.handle_new_pod(pod_b)
wd.handle_new_policy(pol)

check("no rule created - segmentation isolates n-a from n-b despite the allowing policy", len(remotes_of("SG_n-a")) == 0)


# ============================================================
# Scenario C: regression check - a pair in the SAME segment (or no
# segmentation at all) must still connect normally. This feature must not
# become a blanket lockdown.
# ============================================================
print("\n=== Scenario C: same-segment pair still connects normally ===")
reset_all()
wd, pol, pod_a, pod_b = setup_two_node_pair()
ClusterState.set_node_segments({"n-a": "seg-1", "n-b": "seg-1"}, isolated=True)

wd.handle_new_pod(pod_a)
wd.handle_new_pod(pod_b)
wd.handle_new_policy(pol)

check("rule IS created - n-a and n-b are in the same segment", len(remotes_of("SG_n-a")) == 1)


# ============================================================
# Scenario D: revoke_rules_for_isolated_pairs() tears down an ALREADY-created
# rule once a segmentation update newly isolates that pair - isolation must
# be enforced retroactively, not just gate future connections.
# ============================================================
print("\n=== Scenario D: existing rule is revoked when segmentation newly isolates the pair ===")
reset_all()
wd, pol, pod_a, pod_b = setup_two_node_pair()
# No isolation yet - connection is created normally.
wd.handle_new_pod(pod_a)
wd.handle_new_pod(pod_b)
wd.handle_new_policy(pol)
check("rule exists before any segmentation is applied", len(remotes_of("SG_n-a")) == 1)

SecurityGroupModulePNS.revoke_rules_for_isolated_pairs({("n-a", "n-b")})
check("rule revoked once the pair is (simulated) newly isolated", len(remotes_of("SG_n-a")) == 0)

# Revoking again (idempotency - e.g. a second unrelated segmentation update
# still lists this same already-isolated pair) must not raise or misbehave.
try:
    SecurityGroupModulePNS.revoke_rules_for_isolated_pairs({("n-a", "n-b")})
    check("revoking an already-revoked pair is a harmless no-op", True)
except Exception as e:
    check(f"revoking an already-revoked pair is a harmless no-op (raised {e})", False)


# ============================================================
# Scenario E: main_operator.sync_node_segments_from_nsp() wiring - the actual
# on.resume/on.field entrypoint - drives both the ClusterState cache AND
# retroactive revocation from a raw NodeSegmentationPolicy CR body. The
# ConfigMap publish is mocked out - it must never make a real cluster call in
# a unit test regardless of the local kubeconfig.
# ============================================================
print("\n=== Scenario E: sync_node_segments_from_nsp() end-to-end from a CR body ===")
reset_all()
wd, pol, pod_a, pod_b = setup_two_node_pair()
wd.handle_new_pod(pod_a)
wd.handle_new_pod(pod_b)
wd.handle_new_policy(pol)
check("rule exists before the NSP CR is ever seen", len(remotes_of("SG_n-a")) == 1)

with mock.patch("main_operator.publish_connectivity_configmap") as mock_publish:
    body = {
        "spec": {"isolated": True},
        "status": {"segments": [{"name": "seg-1", "nodes": ["n-a"]}, {"name": "seg-2", "nodes": ["n-b"]}]},
    }
    main_operator.sync_node_segments_from_nsp(body)
    check("ConfigMap publish was attempted", mock_publish.called)

check("ClusterState now reflects the new segments", ClusterState.is_isolated("n-a", "n-b"))
check("the pre-existing rule was retroactively revoked", len(remotes_of("SG_n-a")) == 0)

with mock.patch("main_operator.publish_connectivity_configmap"):
    main_operator.sync_node_segments_from_nsp({"spec": {"isolated": False}, "status": {}})
check("turning isolation off clears the cache", not ClusterState.is_isolated("n-a", "n-b"))


# ============================================================
# Scenario F: connectivity_configmap_data()'s key/value shape - mirrors
# Nestor-paper's netperf-metrics ConfigMap key convention.
# ============================================================
print("\n=== Scenario F: connectivity ConfigMap data shape ===")
data = main_operator.connectivity_configmap_data({}, False)
check("isolation off -> no ConfigMap entries at all", data == {})

data = main_operator.connectivity_configmap_data({"n-a": "seg-1", "n-b": "seg-2", "n-c": "seg-1"}, True)
check("key shape matches the origin/destination convention",
      data.get("grasshopper.connection.boolean.origin.n-a.destination.n-b") == "0")
check("same-segment pair is marked allowed (1)",
      data.get("grasshopper.connection.boolean.origin.n-a.destination.n-c") == "1")
check("different-segment pair is marked blocked (0), both directions",
      data.get("grasshopper.connection.boolean.origin.n-b.destination.n-a") == "0")
check("no self-pair entries", "grasshopper.connection.boolean.origin.n-a.destination.n-a" not in data)
check("exactly 6 entries for 3 nodes (3x2 ordered pairs, no self-pairs)", len(data) == 6)


report_and_exit()
