"""
Documents and verifies, end to end, that this branch's multi-domain support
is fully backward compatible with a plain single-OpenStack-project
deployment - i.e. a cluster with just ONE clouds.yaml-derived credentials
Secret (the flat OS_AUTH_URL/OS_APPLICATION_CREDENTIAL_ID/etc. env vars,
never OS_PROJECTS_JSON) and no `grasshopper.io/openstack-project` label on
any node. See README_v2.md, "Any node without this label is treated as
belonging to the 'default' project."

Unlike verify_multidomain.py's Scenario A (which checks OpenStackClient's
credential fallback in isolation), this exercises the whole pipeline a real
single-project cluster would hit: node-label reading, create_master_and_workerSG(),
and the dynamic per-pod/per-policy path - confirming none of it ever takes a
multi-domain-specific branch (no CIDR rules, no second project, no phantom
project keys) when there's genuinely only one project to know about.

Run with: python verify_single_project_fallback.py
"""
import types
import unittest.mock as mock

import _bootstrap
from _bootstrap import check, report_and_exit

from classes import CIDR, Node, SecurityGroup, node_project_from_labels
from cluster_state import ClusterState
from watchdog import WatchDog
from openstackfiles.openstack_client import OpenStackClient
from operator_code.watcher_operator import Watcher

import os

import openstackfiles.create_master_and_workerSG as cmw


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
    for key in ("OS_PROJECTS_JSON", "OS_AUTH_URL", "OS_APPLICATION_CREDENTIAL_ID",
                "OS_APPLICATION_CREDENTIAL_SECRET", "OS_NEUTRON_ENDPOINT", "OS_NOVA_ENDPOINT"):
        os.environ.pop(key, None)
    os.environ["OS_AUTH_URL"] = "https://legacy.example.com:5000"
    os.environ["OS_APPLICATION_CREDENTIAL_ID"] = "legacy-id"
    os.environ["OS_APPLICATION_CREDENTIAL_SECRET"] = "legacy-secret"


def pod_dict(name, ns, labels, node):
    return {"metadata": {"name": name, "namespace": ns, "labels": labels}, "spec": {"nodeName": node}}


def pol_dict(name, ns, sel, allow, port=80, protocol="TCP"):
    return {
        "metadata": {"name": name, "namespace": ns},
        "spec": {"podSelector": {"matchLabels": sel}, "ingress": [{"from": [{"podSelector": {"matchLabels": allow}}], "ports": [{"port": port, "protocol": protocol}]}]},
    }


# ============================================================
# Step 1: a node with NO grasshopper.io/openstack-project label at all -
# exactly what every node in a single-project cluster looks like - resolves
# to "default", matching OpenStackClient's own fallback credential key.
# ============================================================
print("=== Step 1: unlabeled node resolves to the 'default' project ===")
check("node_project_from_labels({}) == 'default'", node_project_from_labels({}) == "default")
check("node_project_from_labels(None) == 'default'", node_project_from_labels(None) == "default")
check("a node with unrelated labels (no openstack-project key) still == 'default'",
      node_project_from_labels({"kubernetes.io/hostname": "worker-1"}) == "default")


# ============================================================
# Step 2: with no OS_PROJECTS_JSON set, there is exactly one known project,
# built from the same flat env vars a pre-multi-domain deployment already
# has - no second project is ever assumed to exist.
# ============================================================
print("\n=== Step 2: exactly one known project, from the flat env vars ===")
reset_all()
check("known_project_keys() == ['default']", OpenStackClient.known_project_keys() == ["default"])
check("for_project() with no args also resolves to 'default'",
      OpenStackClient.for_project().project_key == "default")


# ============================================================
# Step 3: create_master_and_workerSG() with entirely unlabeled nodes -
# masterSG/workerSG are created in exactly one project, wired with plain
# remote_group_id rules (the original, pre-multi-domain shape) - never CIDR,
# since there is no second project for anything to be "cross" of.
# ============================================================
print("\n=== Step 3: create_master_and_workerSG() with no node labels at all ===")
reset_all()


class FakeAddr:
    def __init__(self, ip):
        self.type = "InternalIP"
        self.address = ip


class FakeNode:
    def __init__(self, name, ip):
        # No grasshopper.io/openstack-project key anywhere - a real
        # single-project cluster's nodes never carry this label.
        self.metadata = types.SimpleNamespace(name=name, labels={})
        self.status = types.SimpleNamespace(addresses=[FakeAddr(ip)])


nodes = [
    FakeNode("master-1", "10.0.0.1"),
    FakeNode("worker-1", "10.0.0.10"),
    FakeNode("worker-2", "10.0.0.11"),
]
# Only the control-plane label is set - no grasshopper.io/openstack-project
# label anywhere, exactly like a real single-project cluster's nodes.
nodes[0].metadata.labels = {cmw.master_node_label: "true"}

created_sgs = {}
created_rules = []


def make_fake_neutron(project_key):
    neutron = mock.MagicMock()

    def list_security_groups(name=None):
        key = (project_key, name)
        if key in created_sgs:
            return {"security_groups": [created_sgs[key]]}
        return {"security_groups": []}

    def create_security_group(body):
        name = body["security_group"]["name"]
        sg = {"id": f"{project_key}-{name}-id", "name": name}
        created_sgs[(project_key, name)] = sg
        return {"security_group": sg}

    def create_security_group_rule(body):
        r = body["security_group_rule"]
        created_rules.append((r["security_group_id"], r["direction"], r.get("remote_group_id"), r.get("remote_ip_prefix")))
        return {"security_group_rule": {"id": f"rule-{len(created_rules)}"}}

    neutron.list_security_groups.side_effect = list_security_groups
    neutron.create_security_group.side_effect = create_security_group
    neutron.list_security_group_rules.return_value = {"security_group_rules": []}
    neutron.create_security_group_rule.side_effect = create_security_group_rule
    return neutron


def make_fake_nova(project_key):
    nova = mock.MagicMock()

    def find(name):
        server = mock.MagicMock()
        server.list_security_group.return_value = []
        return server

    nova.servers.find.side_effect = find
    return nova


def fake_for_project(project_key):
    client_obj = mock.MagicMock()
    client_obj.get_neutron.return_value = make_fake_neutron(project_key)
    client_obj.get_nova.return_value = make_fake_nova(project_key)
    return client_obj


with mock.patch.object(OpenStackClient, "for_project", side_effect=fake_for_project), \
     mock.patch("kubernetes.config.load_kube_config"), \
     mock.patch("kubernetes.client.CoreV1Api") as MockCoreV1:
    MockCoreV1.return_value.list_node.return_value = types.SimpleNamespace(items=nodes)
    cmw.create_master_and_workerSG()

check("masterSG created in exactly one project ('default')",
      [k for k in created_sgs if k[1] == "masterSG"] == [("default", "masterSG")])
check("workerSG created in exactly one project ('default')",
      [k for k in created_sgs if k[1] == "workerSG"] == [("default", "workerSG")])
check("master<->worker rules use remote_group_id (the same-project shape)",
      any(r[2] is not None for r in created_rules))
# A few rules legitimately target 0.0.0.0/0 ("to any" - SSH/DNS/HTTPS), unrelated
# to multi-domain. What must NEVER appear in a single-project deployment is a
# CIDR tied to a SPECIFIC peer node's own IP (/32) - that shape only exists for
# the cross-project branch, which a single "default" project can never reach.
check("no rule targets a specific peer node's IP via CIDR (the cross-project-only shape)",
      not any(r[3] and r[3] != "0.0.0.0/0" for r in created_rules))


# ============================================================
# Step 4: the dynamic per-pod/per-policy path - two pods matching a
# NetworkPolicy, on two different (both unlabeled) nodes, must produce a
# plain SecurityGroup-target rule, never a CIDR. This is the same check
# verify_multidomain.py's Scenario C does explicitly with project="proj-a"
# on both sides; here nothing is labeled at all, which is the actual shape
# of every node in a real single-project cluster.
# ============================================================
print("\n=== Step 4: dynamic NetworkPolicy rule between two unlabeled nodes ===")
reset_all()
wd = WatchDog(PNS_scenario=True)

for name, ip in (("node-a", "10.0.0.20"), ("node-b", "10.0.0.21")):
    ClusterState.add_node(Node(name, project=node_project_from_labels({}), internal_ip=ip))
ClusterState.add_security_group(SecurityGroup(id="sg-a-id", name="SG_node-a", project="default"))
ClusterState.add_security_group(SecurityGroup(id="sg-b-id", name="SG_node-b", project="default"))

pol = Watcher.create_policy_from_policy_dict(pol_dict("pol", "ns", {"app": "server"}, {"app": "client"}, port=80))
pod_server = Watcher.create_pod_from_pod_dict(pod_dict("server-1", "ns", {"app": "server"}, "node-a"))
pod_client = Watcher.create_pod_from_pod_dict(pod_dict("client-1", "ns", {"app": "client"}, "node-b"))

wd.handle_new_policy(pol)
wd.handle_new_pod(pod_server)
wd.handle_new_pod(pod_client)

remotes = ClusterState.get_security_group("SG_node-a").remotes
check("exactly one rule created on the server's SG", len(remotes) == 1)
rule = next(iter(remotes))
check("rule target is the peer's SecurityGroup (remote_group_id shape)", isinstance(rule.target, SecurityGroup))
check("rule target is NOT a CIDR - the cross-project branch was never taken", not isinstance(rule.target, CIDR))
check("rule target is specifically SG_node-b", rule.target.name == "SG_node-b")
check("rule port is the policy's real port (80), no VXLAN substitution", rule.traffic.port == 80)


report_and_exit()
