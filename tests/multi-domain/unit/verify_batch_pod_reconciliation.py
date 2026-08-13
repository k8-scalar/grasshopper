"""
Verifies WatchDog.handle_new_pods_batch()/handle_removed_pods_batch() - the
batch-computation path reconcile_pods_once() uses. The key property these
add over calling handle_new_pod()/handle_removed_pod() once per pod is NOT a
different end state (SG_config_new_pod/remove_pod are already deduped per
(labelset, node) pair either way - see handle_new_pod's own match_nodes
check) - it's that the batch methods reach that same end state with far
fewer lock acquisitions and OpenStack calls when many pods in the batch share
nodes. This is exactly what a 1000-pod burst needs: computing the eventual
configuration for the whole group in memory, rather than serializing through
N individual lock-acquire-and-maybe-call cycles that under load can stall
behind a single slow call (confirmed live - see main.md/session notes).

Covers, with the real WatchDog/ClusterState pipeline and only the OpenStack
calls mocked:
- A batch of pods spread across multiple nodes converges to the correct
  minimal rule set - one rule per distinct node pair, not one per pod.
- The underlying create_security_group_rule call count matches the number of
  distinct node pairs, NOT the number of pods - the actual efficiency claim,
  not just the end state (which alone wouldn't distinguish this from the
  old per-pod loop).
- Already-tracked pods in a batch are skipped (idempotent, matches
  handle_new_pod's own "already exists" guard).
- Batch removal correctly reference-counts: a node with another surviving
  pod on the same labelset keeps its rule; a node with none gets it revoked.
- Removing a batch that spans multiple nodes issues exactly one
  delete_security_group_rule call per node that actually lost coverage.

Run with: python verify_batch_pod_reconciliation.py
"""
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

created_rule_calls = []
removed_rule_calls = []


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
    created_rule_calls.clear()
    removed_rule_calls.clear()


def pod_dict(name, ns, labels, node):
    return {"metadata": {"name": name, "namespace": ns, "labels": labels}, "spec": {"nodeName": node}}


def pol_dict(name, ns, sel, allow, port=8080):
    return {
        "metadata": {"name": name, "namespace": ns},
        "spec": {"podSelector": {"matchLabels": sel}, "ingress": [{"from": allow, "ports": [{"port": port, "protocol": "TCP"}]}]},
    }


def remotes_of(sg_name):
    return ClusterState.get_security_group(sg_name).remotes


def make_fake_neutron():
    neutron = mock.MagicMock()

    def create_security_group_rule(body):
        r = body["security_group_rule"]
        created_rule_calls.append((r["security_group_id"], r.get("remote_group_id")))
        return {"security_group_rule": {"id": f"rule-{len(created_rule_calls)}"}}

    def delete_security_group_rule(security_group_rule):
        removed_rule_calls.append(security_group_rule)

    neutron.create_security_group_rule.side_effect = create_security_group_rule
    neutron.delete_security_group_rule.side_effect = delete_security_group_rule
    return neutron


# Patched once for the whole file - every scenario reuses the same counting
# neutron mock, reset via reset_all()'s created_rule_calls.clear().
_neutron_patch = mock.patch.object(OpenStackClient, "for_project", return_value=mock.MagicMock(get_neutron=make_fake_neutron))
_neutron_patch.start()


def setup_cluster(node_names, sg_names=None):
    for name in node_names:
        ClusterState.add_node(Node(name, project="default", internal_ip=f"10.0.0.{node_names.index(name) + 1}"))
        ClusterState.add_security_group(SecurityGroup(id=f"sg-{name}", name=f"SG_{name}", project="default"))


def make_policy_and_pods(server_nodes, client_nodes, port=8080):
    """
    One policy allowing app=client -> app=server, one server pod per node in
    server_nodes and one client pod per node in client_nodes (named after
    their node for readability). Returns (policy, server_pods, client_pods).
    """
    pol = Watcher.create_policy_from_policy_dict(
        pol_dict("allow-client-to-server", "ns1", {"app": "server"}, [{"podSelector": {"matchLabels": {"app": "client"}}}], port=port)
    )
    server_pods = [Watcher.create_pod_from_pod_dict(pod_dict(f"server-{n}", "ns1", {"app": "server"}, n)) for n in server_nodes]
    client_pods = [Watcher.create_pod_from_pod_dict(pod_dict(f"client-{n}", "ns1", {"app": "client"}, n)) for n in client_nodes]
    return pol, server_pods, client_pods


# ============================================================
# Scenario A: a batch of server pods spread across 3 nodes, plus 2 client
# pods on 1 more node each - converges to exactly 3 rules (one per distinct
# server node), with exactly 3 create_security_group_rule calls, not 5 (the
# total pod count) and not more.
# ============================================================
print("=== Scenario A: batch across multiple nodes converges with minimal OpenStack calls ===")
reset_all()
setup_cluster(["n-srv-1", "n-srv-2", "n-srv-3", "n-cli-1"])
wd = WatchDog(PNS_scenario=True)
pol, server_pods, client_pods = make_policy_and_pods(["n-srv-1", "n-srv-2", "n-srv-3"], ["n-cli-1"])
wd.handle_new_policy(pol)

wd.handle_new_pods_batch(set(server_pods) | set(client_pods))

check("all 4 pods now tracked", len(ClusterState.get_pods()) == 4)
check("exactly 3 rules exist (one per server node)",
      sum(len(remotes_of(f"SG_n-srv-{i}")) for i in (1, 2, 3)) == 3)
check("exactly 3 create_security_group_rule calls - not 4 (pod count)", len(created_rule_calls) == 3)
for i in (1, 2, 3):
    rule = next(iter(remotes_of(f"SG_n-srv-{i}")))
    check(f"n-srv-{i}'s rule targets SG_n-cli-1", rule.target.name == "SG_n-cli-1")


# ============================================================
# Scenario B: several pods landing on the SAME node - must not create
# duplicate rules or repeat OpenStack calls beyond the one node actually
# needs.
# ============================================================
print("\n=== Scenario B: multiple pods on the same node dedupe to one call ===")
reset_all()
setup_cluster(["n-srv-1", "n-cli-1"])
wd = WatchDog(PNS_scenario=True)
pol = Watcher.create_policy_from_policy_dict(
    pol_dict("allow-client-to-server", "ns1", {"app": "server"}, [{"podSelector": {"matchLabels": {"app": "client"}}}])
)
wd.handle_new_policy(pol)
server_pods = [Watcher.create_pod_from_pod_dict(pod_dict(f"server-{i}", "ns1", {"app": "server"}, "n-srv-1")) for i in range(5)]
client_pod = Watcher.create_pod_from_pod_dict(pod_dict("client-1", "ns1", {"app": "client"}, "n-cli-1"))

wd.handle_new_pods_batch(set(server_pods) | {client_pod})

check("all 6 pods tracked despite sharing one node", len(ClusterState.get_pods()) == 6)
check("exactly one rule exists on SG_n-srv-1", len(remotes_of("SG_n-srv-1")) == 1)
check("exactly one create_security_group_rule call - not 5", len(created_rule_calls) == 1)


# ============================================================
# Scenario C: already-tracked pods in a batch are skipped entirely - mixing
# a genuinely new pod with an already-known one must not re-touch the known
# one or re-issue its rule.
# ============================================================
print("\n=== Scenario C: already-tracked pods in the batch are left alone ===")
reset_all()
setup_cluster(["n-srv-1", "n-srv-2", "n-cli-1"])
wd = WatchDog(PNS_scenario=True)
pol, server_pods, client_pods = make_policy_and_pods(["n-srv-1"], ["n-cli-1"])
wd.handle_new_policy(pol)
wd.handle_new_pod(server_pods[0])
wd.handle_new_pod(client_pods[0])
check("baseline: one rule exists before the batch call", len(remotes_of("SG_n-srv-1")) == 1)
created_rule_calls.clear()

new_server_pod = Watcher.create_pod_from_pod_dict(pod_dict("server-n-srv-2", "ns1", {"app": "server"}, "n-srv-2"))
wd.handle_new_pods_batch({server_pods[0], new_server_pod})  # server_pods[0] already tracked

check("the already-tracked pod was not duplicated", len(ClusterState.get_pods()) == 3)
check("only the genuinely new node's rule was created", len(created_rule_calls) == 1)
check("SG_n-srv-1 still has exactly its original rule (untouched)", len(remotes_of("SG_n-srv-1")) == 1)
check("SG_n-srv-2 now has its rule too", len(remotes_of("SG_n-srv-2")) == 1)


# ============================================================
# Scenario D: batch removal reference-counts correctly - removing every
# server pod on a node revokes its rule; a node that still has a surviving
# pod on the same labelset keeps its rule.
# ============================================================
print("\n=== Scenario D: batch removal - reference counting across nodes ===")
reset_all()
setup_cluster(["n-srv-1", "n-srv-2", "n-cli-1"])
wd = WatchDog(PNS_scenario=True)
pol = Watcher.create_policy_from_policy_dict(
    pol_dict("allow-client-to-server", "ns1", {"app": "server"}, [{"podSelector": {"matchLabels": {"app": "client"}}}])
)
wd.handle_new_policy(pol)
# n-srv-1 gets TWO server pods (one will survive), n-srv-2 gets ONE (will be fully removed).
srv1_a = Watcher.create_pod_from_pod_dict(pod_dict("server-1a", "ns1", {"app": "server"}, "n-srv-1"))
srv1_b = Watcher.create_pod_from_pod_dict(pod_dict("server-1b", "ns1", {"app": "server"}, "n-srv-1"))
srv2_a = Watcher.create_pod_from_pod_dict(pod_dict("server-2a", "ns1", {"app": "server"}, "n-srv-2"))
client_pod = Watcher.create_pod_from_pod_dict(pod_dict("client-1", "ns1", {"app": "client"}, "n-cli-1"))
wd.handle_new_pods_batch({srv1_a, srv1_b, srv2_a, client_pod})
check("baseline: both server nodes have a rule", len(remotes_of("SG_n-srv-1")) == 1 and len(remotes_of("SG_n-srv-2")) == 1)
created_rule_calls.clear()

# Remove server-1a (n-srv-1 survives via server-1b) AND server-2a (n-srv-2 has nothing left) together.
wd.handle_removed_pods_batch({srv1_a, srv2_a})

check("server-1a and server-2a no longer tracked", srv1_a not in ClusterState.get_pods() and srv2_a not in ClusterState.get_pods())
check("server-1b is still tracked", srv1_b in ClusterState.get_pods())
check("n-srv-1's rule SURVIVES - server-1b still matches there", len(remotes_of("SG_n-srv-1")) == 1)
check("n-srv-2's rule is REVOKED - nothing matches there anymore", len(remotes_of("SG_n-srv-2")) == 0)
check("exactly one delete_security_group_rule call - only n-srv-2 actually lost coverage", len(removed_rule_calls) == 1)


_neutron_patch.stop()
report_and_exit()
