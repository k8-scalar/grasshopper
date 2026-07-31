"""
Verifies the pod/policy removal race fix in security_group_module.py /
helpers.py (SG_remove_conn's guard). Exercises the real, unmodified
WatchDog/matcher code with only the OpenStack (neutron) calls mocked.

Run with: python verify_removal_race_fix.py
"""
import os
import threading

import _bootstrap
from _bootstrap import check, report_and_exit

from classes import Node, SecurityGroup
from cluster_state import ClusterState
from watchdog import WatchDog
from openstackfiles.openstack_client import OpenStackClient
from operator_code.watcher_operator import Watcher

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


def pod_dict(name, ns, labels, node):
    return {"metadata": {"name": name, "namespace": ns, "labels": labels}, "spec": {"nodeName": node}}


def pol_dict(name, ns, sel, allow, port=8080):
    return {
        "metadata": {"name": name, "namespace": ns},
        "spec": {"podSelector": {"matchLabels": sel}, "ingress": [{"from": allow, "ports": [{"port": port, "protocol": "TCP"}]}]},
    }


def remotes_of(sg_name):
    return ClusterState.get_security_group(sg_name).remotes


# ============================================================
# Scenario A: pod removed BEFORE policy removed (the exact failing order found live)
# ============================================================
print("=== Scenario A: pod-a removed fully before policy removal ===")
reset_all()
wd = WatchDog(PNS_scenario=True)
n_a, n_b = Node("n-a", project="default", internal_ip="10.0.0.1"), Node("n-b", project="default", internal_ip="10.0.0.2")
ClusterState.add_node(n_a); ClusterState.add_node(n_b)
ClusterState.add_security_group(SecurityGroup(id="sg-a", name="SG_n-a", project="default"))
ClusterState.add_security_group(SecurityGroup(id="sg-b", name="SG_n-b", project="default"))

pol = Watcher.create_policy_from_policy_dict(pol_dict("allow-b-to-a", "ns1", {"app": "server-a"}, [{"podSelector": {"matchLabels": {"app": "client-b"}}}]))
pod_a = Watcher.create_pod_from_pod_dict(pod_dict("pod-a", "ns1", {"app": "server-a"}, "n-a"))
pod_b = Watcher.create_pod_from_pod_dict(pod_dict("pod-b", "ns1", {"app": "client-b"}, "n-b"))
wd.handle_new_pod(pod_a)
wd.handle_new_pod(pod_b)
wd.handle_new_policy(pol)
check("rule exists after setup", len(remotes_of("SG_n-a")) == 1)

wd.handle_removed_pod(pod_a)
wd.handle_removed_policy(pol)
check("rule removed when pod-a is removed BEFORE the policy", len(remotes_of("SG_n-a")) == 0)


# ============================================================
# Scenario B: pod-b (the peer) removed before policy removal
# ============================================================
print("\n=== Scenario B: pod-b removed fully before policy removal ===")
reset_all()
wd = WatchDog(PNS_scenario=True)
ClusterState.add_node(Node("n-a", project="default", internal_ip="10.0.0.1"))
ClusterState.add_node(Node("n-b", project="default", internal_ip="10.0.0.2"))
ClusterState.add_security_group(SecurityGroup(id="sg-a", name="SG_n-a", project="default"))
ClusterState.add_security_group(SecurityGroup(id="sg-b", name="SG_n-b", project="default"))

pol = Watcher.create_policy_from_policy_dict(pol_dict("allow-b-to-a", "ns1", {"app": "server-a"}, [{"podSelector": {"matchLabels": {"app": "client-b"}}}]))
pod_a = Watcher.create_pod_from_pod_dict(pod_dict("pod-a", "ns1", {"app": "server-a"}, "n-a"))
pod_b = Watcher.create_pod_from_pod_dict(pod_dict("pod-b", "ns1", {"app": "client-b"}, "n-b"))
wd.handle_new_pod(pod_a)
wd.handle_new_pod(pod_b)
wd.handle_new_policy(pol)

wd.handle_removed_pod(pod_b)
wd.handle_removed_policy(pol)
check("rule removed when pod-b (peer) is removed BEFORE the policy", len(remotes_of("SG_n-a")) == 0)


# ============================================================
# Scenario C: policy removed first (already-working order, must still work)
# ============================================================
print("\n=== Scenario C: policy removed before either pod (already-working order) ===")
reset_all()
wd = WatchDog(PNS_scenario=True)
ClusterState.add_node(Node("n-a", project="default", internal_ip="10.0.0.1"))
ClusterState.add_node(Node("n-b", project="default", internal_ip="10.0.0.2"))
ClusterState.add_security_group(SecurityGroup(id="sg-a", name="SG_n-a", project="default"))
ClusterState.add_security_group(SecurityGroup(id="sg-b", name="SG_n-b", project="default"))

pol = Watcher.create_policy_from_policy_dict(pol_dict("allow-b-to-a", "ns1", {"app": "server-a"}, [{"podSelector": {"matchLabels": {"app": "client-b"}}}]))
pod_a = Watcher.create_pod_from_pod_dict(pod_dict("pod-a", "ns1", {"app": "server-a"}, "n-a"))
pod_b = Watcher.create_pod_from_pod_dict(pod_dict("pod-b", "ns1", {"app": "client-b"}, "n-b"))
wd.handle_new_pod(pod_a)
wd.handle_new_pod(pod_b)
wd.handle_new_policy(pol)

wd.handle_removed_policy(pol)
wd.handle_removed_pod(pod_a)
wd.handle_removed_pod(pod_b)
check("rule removed when policy is removed first", len(remotes_of("SG_n-a")) == 0)


# ============================================================
# Scenario D: a DIFFERENT policy genuinely still needs the same traffic -
# the guard must still correctly block removal in this legitimate case.
# ============================================================
print("\n=== Scenario D: a different policy still needs the connection - must NOT remove ===")
reset_all()
wd = WatchDog(PNS_scenario=True)
ClusterState.add_node(Node("n-a", project="default", internal_ip="10.0.0.1"))
ClusterState.add_node(Node("n-b", project="default", internal_ip="10.0.0.2"))
ClusterState.add_security_group(SecurityGroup(id="sg-a", name="SG_n-a", project="default"))
ClusterState.add_security_group(SecurityGroup(id="sg-b", name="SG_n-b", project="default"))

# Two INDEPENDENT policies (different, non-subset selectors so neither is
# flagged redundant/conflicting with the other) that both happen to require
# server-a <- client-b traffic on the same port, via a pod carrying both labels.
pol1 = Watcher.create_policy_from_policy_dict(pol_dict("allow-b-to-a-1", "ns1", {"app": "server-a"}, [{"podSelector": {"matchLabels": {"app": "client-b"}}}], port=8080))
pol2 = Watcher.create_policy_from_policy_dict(pol_dict("allow-b-to-a-2", "ns1", {"tier": "backend"}, [{"podSelector": {"matchLabels": {"app": "client-b"}}}], port=8080))
pod_a = Watcher.create_pod_from_pod_dict(pod_dict("pod-a", "ns1", {"app": "server-a", "tier": "backend"}, "n-a"))
pod_b = Watcher.create_pod_from_pod_dict(pod_dict("pod-b", "ns1", {"app": "client-b"}, "n-b"))
wd.handle_new_pod(pod_a)
wd.handle_new_pod(pod_b)
wd.handle_new_policy(pol1)
wd.handle_new_policy(pol2)
check("rule exists after both policies applied", len(remotes_of("SG_n-a")) == 1)

# Remove only pol1 - pol2 still needs the connection, so it must survive.
wd.handle_removed_policy(pol1)
check("rule SURVIVES removal of pol1 because pol2 still needs it", len(remotes_of("SG_n-a")) == 1)

# Now remove pol2 too - nothing needs it anymore, rule must go.
wd.handle_removed_policy(pol2)
check("rule removed once the LAST policy needing it is removed", len(remotes_of("SG_n-a")) == 0)


# ============================================================
# Scenario E: original concurrent/threaded race, repeated many times
# ============================================================
print("\n=== Scenario E: concurrent removal (threaded), repeated 20x ===")
races_lost = 0
for trial in range(20):
    reset_all()
    wd = WatchDog(PNS_scenario=True)
    ClusterState.add_node(Node("n-a", project="default", internal_ip="10.0.0.1"))
    ClusterState.add_node(Node("n-b", project="default", internal_ip="10.0.0.2"))
    ClusterState.add_security_group(SecurityGroup(id="sg-a", name="SG_n-a", project="default"))
    ClusterState.add_security_group(SecurityGroup(id="sg-b", name="SG_n-b", project="default"))
    pol = Watcher.create_policy_from_policy_dict(pol_dict("allow-b-to-a", "ns1", {"app": "server-a"}, [{"podSelector": {"matchLabels": {"app": "client-b"}}}]))
    pod_a = Watcher.create_pod_from_pod_dict(pod_dict("pod-a", "ns1", {"app": "server-a"}, "n-a"))
    pod_b = Watcher.create_pod_from_pod_dict(pod_dict("pod-b", "ns1", {"app": "client-b"}, "n-b"))
    wd.handle_new_pod(pod_a)
    wd.handle_new_pod(pod_b)
    wd.handle_new_policy(pol)

    barrier = threading.Barrier(3)
    def remove_pod_a():
        barrier.wait(); wd.handle_removed_pod(pod_a)
    def remove_pod_b():
        barrier.wait(); wd.handle_removed_pod(pod_b)
    def remove_policy():
        barrier.wait(); wd.handle_removed_policy(pol)

    threads = [threading.Thread(target=fn) for fn in (remove_pod_a, remove_pod_b, remove_policy)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=5)

    if len(remotes_of("SG_n-a")) != 0:
        races_lost += 1

check(f"0 stale rules across 20 concurrent trials (got {races_lost} failures)", races_lost == 0)


report_and_exit()
