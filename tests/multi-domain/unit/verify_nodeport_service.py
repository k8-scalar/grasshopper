"""
Verifies NodePort Service handling (watchdog.py's handle_new_service/
handle_removed_service, cluster_state.py's worker_security_groups) against
formalization.tex: a rule for a NodePort Service's port must be inserted into
the least-privilege Security Group linked to every worker Node (workerSG) in
each OpenStack project that has a matching Pod, and purged when the Service
itself is deleted.

Covers both possible orderings of the Service/Pod events (a real race - kopf
delivers them independently), multiple OpenStack projects, idempotency, and
the specific deadlock risk fixed in handle_new_pod(): a tracked NetworkPolicy
and a NodePort Service can legitimately share the exact same selector (e.g.
both scoped to one service's own label), so the NodePort backfill check in
handle_new_pod() must never nest its own lock inside the pod's main
lock_labelsets(used_labelsets) block.

Run with: python verify_nodeport_service.py
"""
import json
import os

import _bootstrap
from _bootstrap import check, report_and_exit

from classes import CIDR, Node, Rule, SecurityGroup, Traffic, INGRESS
from cluster_state import ClusterState
from watchdog import WatchDog
from openstackfiles.openstack_client import OpenStackClient
from operator_code.watcher_operator import Watcher

os.environ["OS_PROJECTS_JSON"] = json.dumps([
    {"key": "proj-a", "auth_url": "https://a.example.com:5000",
     "application_credential_id": "a-id", "application_credential_secret": "a-secret",
     "neutron_endpoint": "https://a.example.com:9696", "nova_endpoint": "https://a.example.com:8774/v2.1"},
    {"key": "proj-b", "auth_url": "https://b.example.com:5000",
     "application_credential_id": "b-id", "application_credential_secret": "b-secret",
     "neutron_endpoint": "https://b.example.com:9696", "nova_endpoint": "https://b.example.com:8774/v2.1"},
])


def reset_all():
    ClusterState.map.clear()
    ClusterState.nodes.clear()
    ClusterState._nodes_by_name.clear()
    ClusterState.pods.clear()
    ClusterState.policies.clear()
    ClusterState.security_groups.clear()
    ClusterState.worker_security_groups.clear()
    ClusterState.nodeport_services.clear()
    ClusterState.namespaces.clear()
    ClusterState.offenders.clear()
    OpenStackClient._instances.clear()
    OpenStackClient._credentials_by_key = None


def pod_dict(name, ns, labels, node):
    return {"metadata": {"name": name, "namespace": ns, "labels": labels}, "spec": {"nodeName": node}}


def nodeport_svc_dict(name, ns, selector, node_port=30080, protocol="TCP"):
    return {
        "metadata": {"name": name, "namespace": ns},
        "spec": {
            "type": "NodePort",
            "selector": selector,
            "ports": [{"port": 8080, "targetPort": 8080, "nodePort": node_port, "protocol": protocol}],
        },
    }


def nodeport_rule_in(sg_name, port=30080, protocol="TCP"):
    sg = ClusterState.get_security_group(sg_name)
    if sg is None:
        return False
    return Rule(CIDR("0.0.0.0/0"), Traffic(INGRESS, port, protocol)) in sg.remotes


def make_worker_sg(project, name="workerSG"):
    sg = SecurityGroup(id=f"sg-{project}", name=name, project=project)
    ClusterState.add_security_group(sg)
    ClusterState.worker_security_groups[project] = sg
    return sg


# ============================================================
# Scenario A: Pod exists first, then the NodePort Service is created.
# ============================================================
print("=== Scenario A: Pod before Service ===")
reset_all()
wd = WatchDog(PNS_scenario=True)
make_worker_sg("proj-a")
ClusterState.add_node(Node("worker-a1", project="proj-a", internal_ip="10.0.0.1"))

pod = Watcher.create_pod_from_pod_dict(pod_dict("webui-1", "exp3", {"app": "teastore-webui"}, "worker-a1"))
wd.handle_new_pod(pod)

svc = Watcher.create_service_from_dict(nodeport_svc_dict("teastore-webui", "exp3", {"app": "teastore-webui"}))
wd.handle_new_service(svc)

check("rule added to workerSG (proj-a) when the Service arrives after its Pod", nodeport_rule_in("workerSG"))
check("Service tracks proj-a as opened", "proj-a" in ClusterState.get_nodeport_service(svc.key()).opened_projects)


# ============================================================
# Scenario B: the realistic ordering - Service created first (no Pod yet),
# then its Pod gets scheduled. This is the common case: Service+Deployment
# applied together, Pods always lag behind.
# ============================================================
print("\n=== Scenario B: Service before Pod ===")
reset_all()
wd = WatchDog(PNS_scenario=True)
make_worker_sg("proj-a")
ClusterState.add_node(Node("worker-a1", project="proj-a", internal_ip="10.0.0.1"))

svc = Watcher.create_service_from_dict(nodeport_svc_dict("teastore-webui", "exp3", {"app": "teastore-webui"}))
wd.handle_new_service(svc)
check("no rule yet - no matching Pod exists when the Service is created", not nodeport_rule_in("workerSG"))

pod = Watcher.create_pod_from_pod_dict(pod_dict("webui-1", "exp3", {"app": "teastore-webui"}, "worker-a1"))
wd.handle_new_pod(pod)
check("rule added once the matching Pod is scheduled (handle_new_pod backfill)", nodeport_rule_in("workerSG"))


# ============================================================
# Scenario C: matching Pods in two different OpenStack projects - the rule
# must be opened in EACH project's own workerSG.
# ============================================================
print("\n=== Scenario C: matching Pods across two OpenStack projects ===")
reset_all()
wd = WatchDog(PNS_scenario=True)
make_worker_sg("proj-a")
make_worker_sg("proj-b")
ClusterState.add_node(Node("worker-a1", project="proj-a", internal_ip="10.0.0.1"))
ClusterState.add_node(Node("worker-b1", project="proj-b", internal_ip="10.0.1.1"))

svc = Watcher.create_service_from_dict(nodeport_svc_dict("teastore-webui", "exp3", {"app": "teastore-webui"}))
wd.handle_new_service(svc)
wd.handle_new_pod(Watcher.create_pod_from_pod_dict(pod_dict("webui-a", "exp3", {"app": "teastore-webui"}, "worker-a1")))
wd.handle_new_pod(Watcher.create_pod_from_pod_dict(pod_dict("webui-b", "exp3", {"app": "teastore-webui"}, "worker-b1")))

check("rule opened in proj-a's workerSG", nodeport_rule_in("workerSG"))
tracked = ClusterState.get_nodeport_service(svc.key())
check("Service tracks both projects as opened", tracked.opened_projects == {"proj-a", "proj-b"})


# ============================================================
# Scenario D: deleting the Service purges the rule from every project it
# was opened in.
# ============================================================
print("\n=== Scenario D: removing the Service purges the rule everywhere ===")
wd.handle_removed_service(svc)
check("Service no longer tracked after removal", ClusterState.get_nodeport_service(svc.key()) is None)
check("rule purged from proj-a's workerSG", not nodeport_rule_in("workerSG"))


# ============================================================
# Scenario E: idempotency - processing the same Service twice must not
# duplicate the rule or crash (kopf resume/retry can redeliver the same event).
# ============================================================
print("\n=== Scenario E: duplicate Service event is a no-op, not a duplicate ===")
reset_all()
wd = WatchDog(PNS_scenario=True)
make_worker_sg("proj-a")
ClusterState.add_node(Node("worker-a1", project="proj-a", internal_ip="10.0.0.1"))
wd.handle_new_pod(Watcher.create_pod_from_pod_dict(pod_dict("webui-1", "exp3", {"app": "teastore-webui"}, "worker-a1")))

svc = Watcher.create_service_from_dict(nodeport_svc_dict("teastore-webui", "exp3", {"app": "teastore-webui"}))
wd.handle_new_service(svc)
wd.handle_new_service(svc)
check("rule still present exactly once after a duplicate Service event",
      len([r for r in ClusterState.get_security_group("workerSG").remotes
           if r == Rule(CIDR("0.0.0.0/0"), Traffic(INGRESS, 30080, "TCP"))]) == 1)


# ============================================================
# Scenario F: a tracked NetworkPolicy and the NodePort Service share the
# EXACT same selector (a real case: a healthcheck NetworkPolicy and the
# Service it fronts both scoped to one app's own label). handle_new_pod()'s
# used_labelsets lock and the NodePort backfill's own lock must not nest on
# the same labelset, or this deadlocks (the shared LockManager's per-labelset
# locks are plain threading.Lock, not reentrant).
# ============================================================
print("\n=== Scenario F: Service selector collides with a tracked NetworkPolicy selector (deadlock check) ===")
reset_all()
wd = WatchDog(PNS_scenario=True)
make_worker_sg("proj-a")
ClusterState.add_node(Node("worker-a1", project="proj-a", internal_ip="10.0.0.1"))
ClusterState.add_security_group(SecurityGroup(id="sg-worker-a1", name="SG_worker-a1", project="proj-a"))

healthcheck_pol = Watcher.create_policy_from_policy_dict({
    "metadata": {"name": "teastore-webui-healthcheck", "namespace": "exp3"},
    "spec": {
        "podSelector": {"matchLabels": {"app": "teastore-webui"}},
        "ingress": [{"from": [{"ipBlock": {"cidr": "172.22.14.30/32"}}], "ports": [{"port": 8080, "protocol": "TCP"}]}],
    },
})
wd.handle_new_policy(healthcheck_pol)

svc = Watcher.create_service_from_dict(nodeport_svc_dict("teastore-webui", "exp3", {"app": "teastore-webui"}))
wd.handle_new_service(svc)

import threading
done = threading.Event()

def _handle_pod():
    pod = Watcher.create_pod_from_pod_dict(pod_dict("webui-1", "exp3", {"app": "teastore-webui"}, "worker-a1"))
    wd.handle_new_pod(pod)
    done.set()

t = threading.Thread(target=_handle_pod, daemon=True)
t.start()
t.join(timeout=5)
check("handle_new_pod does not deadlock when its NetworkPolicy and a tracked NodePort Service share a selector",
      done.is_set())
check("rule still gets opened despite the shared selector", nodeport_rule_in("workerSG"))


report_and_exit()
