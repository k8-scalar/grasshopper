"""
Verifies the batch reconciliation loop (main_operator.py's reconcile_once()
and friends) - a timing-based safety net that runs alongside, not instead
of, the event-driven kopf handlers. Covers, with the real WatchDog/
ClusterState pipeline and only the Kubernetes/CustomObjects API calls mocked:

- reconcile_pods_once() finds a pod that exists in the cluster but was never
  tracked (a missed create/field event) and handles it as new.
- reconcile_pods_once() finds a pod ClusterState still tracks but that no
  longer exists in the cluster (a missed delete event) and handles it as
  removed.
- reconcile_pods_once() is a no-op when nothing has drifted.
- reconcile_pods_once() does not resurrect a pod that's mid-termination
  (deletion_timestamp set, still returned by the API but blocked on kopf's
  own finalizer).
- reconcile_pods_once() snapshots ClusterState before the API pod listing,
  not after - so a pod added concurrently by its own event handler is never
  misclassified as removed.

This file checks reconcile_pods_once() at the black-box drift-detection
level (untracked/stale pod found -> correctly handled). It doesn't exercise
batches bigger than 2 pods, so it can't distinguish the current batch
computation (WatchDog.handle_new_pods_batch/handle_removed_pods_batch) from
the older one-pod-at-a-time loop it replaced - both converge to the same end
state for a batch this small. See verify_batch_pod_reconciliation.py for the
actual efficiency property (OpenStack call count scales with distinct nodes
in the batch, not pod count) that's the whole point of batching at scale.

Run with: python verify_reconciliation_loop.py
"""
import types
import unittest.mock as mock

import _bootstrap
from _bootstrap import check, report_and_exit

from classes import Node, SecurityGroup
from cluster_state import ClusterState
from watchdog import WatchDog
from openstackfiles.openstack_client import OpenStackClient
from operator_code.watcher_operator import Watcher

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
    OpenStackClient._instances.clear()
    OpenStackClient._credentials_by_key = None
    main_operator.MODE = "PNS"
    main_operator.watchdog = WatchDog(PNS_scenario=True)


def fake_k8s_pod(name, namespace, labels, node_name, deletion_timestamp=None):
    return types.SimpleNamespace(
        metadata=types.SimpleNamespace(name=name, namespace=namespace, labels=labels, deletion_timestamp=deletion_timestamp),
        spec=types.SimpleNamespace(node_name=node_name),
    )


def pol_dict(name, ns, sel, allow, port=8080):
    return {
        "metadata": {"name": name, "namespace": ns},
        "spec": {"podSelector": {"matchLabels": sel}, "ingress": [{"from": allow, "ports": [{"port": port, "protocol": "TCP"}]}]},
    }


def remotes_of(sg_name):
    return ClusterState.get_security_group(sg_name).remotes


def setup_two_node_pair_with_policy():
    ClusterState.add_node(Node("n-a", project="default", internal_ip="10.0.0.1"))
    ClusterState.add_node(Node("n-b", project="default", internal_ip="10.0.0.2"))
    ClusterState.add_security_group(SecurityGroup(id="sg-a", name="SG_n-a", project="default"))
    ClusterState.add_security_group(SecurityGroup(id="sg-b", name="SG_n-b", project="default"))
    pol = Watcher.create_policy_from_policy_dict(pol_dict("allow-b-to-a", "ns1", {"app": "server-a"}, [{"podSelector": {"matchLabels": {"app": "client-b"}}}]))
    main_operator.watchdog.handle_new_policy(pol)
    return pol


# ============================================================
# Scenario A: an untracked pod (missed create event) is picked up and
# handled as new by the batch pass.
# ============================================================
print("=== Scenario A: untracked pod is reconciled as new ===")
reset_all()
setup_two_node_pair_with_policy()

with mock.patch("kubernetes.client.CoreV1Api") as MockCoreV1:
    MockCoreV1.return_value.list_pod_for_all_namespaces.return_value = types.SimpleNamespace(items=[
        fake_k8s_pod("pod-a", "ns1", {"app": "server-a"}, "n-a"),
        fake_k8s_pod("pod-b", "ns1", {"app": "client-b"}, "n-b"),
    ])
    new_count, removed_count = main_operator.reconcile_pods_once()

check("both untracked pods were found and handled", new_count == 2 and removed_count == 0)
check("both pods now tracked in ClusterState", len(ClusterState.get_pods()) == 2)
check("the rule they imply was actually created (not just tracked)", len(remotes_of("SG_n-a")) == 1)

# Re-running immediately, with the same cluster state, must be a no-op -
# reconciliation should never re-process something it already handled.
with mock.patch("kubernetes.client.CoreV1Api") as MockCoreV1:
    MockCoreV1.return_value.list_pod_for_all_namespaces.return_value = types.SimpleNamespace(items=[
        fake_k8s_pod("pod-a", "ns1", {"app": "server-a"}, "n-a"),
        fake_k8s_pod("pod-b", "ns1", {"app": "client-b"}, "n-b"),
    ])
    new_count, removed_count = main_operator.reconcile_pods_once()
check("re-running with no drift finds nothing to do", new_count == 0 and removed_count == 0)
check("rule count is unaffected by the idempotent re-run", len(remotes_of("SG_n-a")) == 1)


# ============================================================
# Scenario B: a pod ClusterState still tracks but that's gone from the
# cluster (missed delete event) is reconciled as removed, and its rule is
# torn down.
# ============================================================
print("\n=== Scenario B: stale tracked pod is reconciled as removed ===")
# Continues from Scenario A's state: pod-a and pod-b both tracked, rule exists.
with mock.patch("kubernetes.client.CoreV1Api") as MockCoreV1:
    MockCoreV1.return_value.list_pod_for_all_namespaces.return_value = types.SimpleNamespace(items=[
        fake_k8s_pod("pod-a", "ns1", {"app": "server-a"}, "n-a"),
        # pod-b is gone - simulates a missed delete event.
    ])
    new_count, removed_count = main_operator.reconcile_pods_once()

check("exactly one stale pod found and handled as removed", new_count == 0 and removed_count == 1)
check("pod-b no longer tracked in ClusterState", len(ClusterState.get_pods()) == 1)
check("its rule was torn down as a consequence", len(remotes_of("SG_n-a")) == 0)


# ============================================================
# Scenario C: a pod that's mid-termination (deletion_timestamp set, still
# blocked on kopf's own finalizer, so still returned by the API) must NOT be
# resurrected by a reconciliation tick that lands after kopf's on.delete
# handler already removed it from ClusterState. Without the
# deletion_timestamp check, this pod would look identical to a genuinely new
# untracked pod - re-adding it to ClusterState and recreating its SG rule,
# flapping it between removed/recreated instead of letting it actually
# terminate. This reproduces a real incident: client-d1 got stuck
# Terminating indefinitely this way during a live elastic test run.
# ============================================================
print("\n=== Scenario C: terminating pod is not resurrected by reconciliation ===")
reset_all()
setup_two_node_pair_with_policy()

# First tick: both pods are genuinely new and untracked - handled as new,
# same as Scenario A.
with mock.patch("kubernetes.client.CoreV1Api") as MockCoreV1:
    MockCoreV1.return_value.list_pod_for_all_namespaces.return_value = types.SimpleNamespace(items=[
        fake_k8s_pod("pod-a", "ns1", {"app": "server-a"}, "n-a"),
        fake_k8s_pod("pod-b", "ns1", {"app": "client-b"}, "n-b"),
    ])
    main_operator.reconcile_pods_once()
check("both pods tracked, rule exists, before simulating termination", len(ClusterState.get_pods()) == 2 and len(remotes_of("SG_n-a")) == 1)

# Simulate kopf's own on.delete handler having already run for pod-b
# (removing it from ClusterState) while the API object itself is still
# present with a deletion_timestamp - the exact race window the bug lives in.
pod_b = next(p for p in ClusterState.get_pods() if p.name == "pod-b")
main_operator.watchdog.handle_removed_pod(pod_b)
check("pod-b removed from ClusterState by the simulated kopf handler", len(ClusterState.get_pods()) == 1)

# The next reconciliation tick still sees pod-b via the API (terminating,
# not yet gone) - it must be skipped, not resurrected.
with mock.patch("kubernetes.client.CoreV1Api") as MockCoreV1:
    MockCoreV1.return_value.list_pod_for_all_namespaces.return_value = types.SimpleNamespace(items=[
        fake_k8s_pod("pod-a", "ns1", {"app": "server-a"}, "n-a"),
        fake_k8s_pod("pod-b", "ns1", {"app": "client-b"}, "n-b", deletion_timestamp="2026-08-13T16:42:00Z"),
    ])
    new_count, removed_count = main_operator.reconcile_pods_once()

check("terminating pod-b was not treated as newly-untracked", new_count == 0)
check("pod-b was not resurrected into ClusterState", len(ClusterState.get_pods()) == 1)
check("pod-b's rule was not recreated", len(remotes_of("SG_n-a")) == 0)


# ============================================================
# Scenario D: a pod whose own event handler adds it to ClusterState WHILE a
# reconciliation tick is mid-flight must not have its brand-new rule torn
# down by that same tick. Reproduces the exact race found live: known is
# read, then (concurrently, in another thread) the pod's own handler adds it
# and creates its rule, then the reconciliation tick's API listing runs and
# of course includes the pod - if known were captured AFTER the API list
# instead of before, this pod would appear in known but not in the
# already-stale actual, misclassified as removed, deleting the rule that
# was just legitimately created moments earlier.
# ============================================================
print("\n=== Scenario D: pod added mid-reconciliation-tick is not torn back down ===")
reset_all()
setup_two_node_pair_with_policy()

# First, directly assert the read order itself - the behavioral race demo
# below can only stress whichever order the code actually uses (the hook
# point is the mocked API call), so on its own it can't tell a correctly-
# ordered implementation apart from a reverted one. This can.
call_order = []
real_get_pods = ClusterState.get_pods


def tracking_get_pods():
    call_order.append("known")
    return real_get_pods()


with mock.patch("cluster_state.ClusterState.get_pods", side_effect=tracking_get_pods), \
     mock.patch("kubernetes.client.CoreV1Api") as MockCoreV1:
    def tracking_list(*_a, **_k):
        call_order.append("actual")
        return types.SimpleNamespace(items=[])
    MockCoreV1.return_value.list_pod_for_all_namespaces.side_effect = tracking_list
    main_operator.reconcile_pods_once()

check("known (ClusterState) is snapshotted before the API pod listing, not after", call_order == ["known", "actual"])

main_operator.watchdog.handle_new_pod(Watcher.create_pod_from_pod_dict({
    "metadata": {"name": "pod-a", "namespace": "ns1", "labels": {"app": "server-a"}},
    "spec": {"nodeName": "n-a"},
}))
check("only pod-a tracked so far, no rule yet (pod-b doesn't exist)", len(ClusterState.get_pods()) == 1 and len(remotes_of("SG_n-a")) == 0)

pod_b_obj = Watcher.create_pod_from_pod_dict({
    "metadata": {"name": "pod-b", "namespace": "ns1", "labels": {"app": "client-b"}},
    "spec": {"nodeName": "n-b"},
})


def list_racing_with_pod_b_creation(*_args, **_kwargs):
    # Simulates pod-b's own event handler finishing - in another thread - in
    # the gap between reconcile_pods_once() reading `known` (only pod-a, at
    # this point) and this API call. By the time the API is actually listed,
    # pod-b genuinely exists (its own handler already saw it there).
    main_operator.watchdog.handle_new_pod(pod_b_obj)
    return types.SimpleNamespace(items=[
        fake_k8s_pod("pod-a", "ns1", {"app": "server-a"}, "n-a"),
        fake_k8s_pod("pod-b", "ns1", {"app": "client-b"}, "n-b"),
    ])


with mock.patch("kubernetes.client.CoreV1Api") as MockCoreV1:
    MockCoreV1.return_value.list_pod_for_all_namespaces.side_effect = list_racing_with_pod_b_creation
    new_count, removed_count = main_operator.reconcile_pods_once()

check("reconciliation did not treat the racing pod-b as removed", removed_count == 0)
check("pod-b is (still) tracked in ClusterState", len(ClusterState.get_pods()) == 2)
check("pod-b's rule survives the racing reconciliation tick", len(remotes_of("SG_n-a")) == 1)


report_and_exit()
