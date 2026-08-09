"""
Verifies the new-node-joins-later fix: main_operator.py's @kopf.on.create('v1',
'nodes') handler (handle_new_node) is gated to PNS mode only, and
create_sg_per_node() - which it calls - actually closes the gap described in
README_v2.md/discussed live: without this, a node that joins after Grasshopper
has already started has no ClusterState Node/SecurityGroup record, so
SGn(n)/rule_from() would crash with an AttributeError on the very first
NetworkPolicy match involving it (SGn() reads ONLY from ClusterState, never
OpenStack directly - creating the SG in OpenStack isn't enough by itself).

Also verifies the "add-if-missing, never overwrite" guarantee this relies on:
re-running create_sg_per_node() (as the handler does, for every node, not just
the new one) must never replace or clear an already-registered node's SG -
that object may carry live .remotes state built up by concurrently running
policy/pod handlers, which a naive resync would race with and clobber.

Run with: python verify_new_node_handler.py
"""
import types
import unittest.mock as mock

import _bootstrap
from _bootstrap import check, report_and_exit

from classes import Rule, SecurityGroup, Traffic
from cluster_state import ClusterState
from openstackfiles.create_sg_per_node import create_sg_per_node
from openstackfiles.openstack_client import OpenStackClient


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


class FakeAddr:
    def __init__(self, ip):
        self.type = "InternalIP"
        self.address = ip


class FakeNode:
    def __init__(self, name, ip, labels=None):
        self.metadata = types.SimpleNamespace(name=name, labels=labels or {})
        self.status = types.SimpleNamespace(addresses=[FakeAddr(ip)])


created_sgs = {}  # (project_key, sg_name) -> fake sg dict, persists across create_sg_per_node() calls


def make_fake_neutron(project_key):
    neutron = mock.MagicMock()

    def list_security_groups(name=None):
        key = (project_key, name)
        if key in created_sgs:
            return {"security_groups": [created_sgs[key]]}
        return {"security_groups": []}

    def create_security_group(body):
        name = body["security_group"]["name"]
        # A freshly created SG already carries Neutron's own default rule(s) -
        # used to confirm create_sg_per_node() actually rebuilds .remotes from
        # whatever OpenStack reports, not just from an empty guess.
        sg = {
            "id": f"{project_key}-{name}-id",
            "name": name,
            "security_group_rules": [
                {"id": "default-egress", "direction": "egress", "protocol": "tcp", "port_range_min": 22, "remote_ip_prefix": "0.0.0.0/0"},
            ],
        }
        created_sgs[(project_key, name)] = sg
        return {"security_group": sg}

    neutron.list_security_groups.side_effect = list_security_groups
    neutron.create_security_group.side_effect = create_security_group
    neutron.delete_security_group_rule.side_effect = lambda security_group_rule: None
    return neutron


def make_fake_nova(project_key, valid_instances):
    nova = mock.MagicMock()

    def find(name):
        if name not in valid_instances:
            raise Exception(f"No server named {name} in project {project_key}")
        server = mock.MagicMock()
        server.list_security_group.return_value = []
        return server

    nova.servers.find.side_effect = find
    return nova


def fake_for_project(project_key, valid_instances):
    client_obj = mock.MagicMock()
    client_obj.get_neutron.return_value = make_fake_neutron(project_key)
    client_obj.get_nova.return_value = make_fake_nova(project_key, valid_instances)
    return client_obj


def run_create_sg_per_node(nodes, valid_instances):
    with mock.patch.object(OpenStackClient, "for_project", side_effect=lambda pk: fake_for_project(pk, valid_instances)), \
         mock.patch("kubernetes.config.load_kube_config"), \
         mock.patch("kubernetes.client.CoreV1Api") as MockCoreV1:
        MockCoreV1.return_value.list_node.return_value = types.SimpleNamespace(items=nodes)
        create_sg_per_node()


# ============================================================
# Scenario A: a genuinely new node (never seen before) - create_sg_per_node()
# must register BOTH its Node and its SecurityGroup in ClusterState, not just
# create/attach the SG in OpenStack.
# ============================================================
print("=== Scenario A: brand new node gets registered in ClusterState ===")
reset_all()
created_sgs.clear()

run_create_sg_per_node([FakeNode("worker-99", "10.0.0.99")], {"worker-99"})

node = ClusterState.get_node("worker-99")
check("new node added to ClusterState", node is not None)
check("new node's project resolved (no label -> 'default')", node is not None and node.project == "default")
check("new node's internal_ip recorded", node is not None and node.internal_ip == "10.0.0.99")

sg = ClusterState.get_security_group("SG_worker-99")
check("new node's SG registered in ClusterState (not just created in OpenStack)", sg is not None)
check("SG's .remotes rebuilt from OpenStack's actual rules, not left empty",
      sg is not None and len(sg.remotes) == 1)
if sg is not None and sg.remotes:
    rule = next(iter(sg.remotes))
    check("rebuilt rule matches OpenStack's real rule (egress/tcp/22)",
          rule.traffic.direction == "egress" and rule.traffic.protocol == "tcp" and rule.traffic.port == 22)


# ============================================================
# Scenario B: re-running create_sg_per_node() (exactly what the new-node kopf
# handler does - it has no way to process only the ONE new node, since
# get_k8s_nodes() always lists everyone) must NOT touch an already-registered
# node/SG, even though it iterates over it again. Simulates the real race this
# guards against: a dynamic rule added by a concurrently running policy/pod
# handler, sitting in .remotes but not yet reflected in OpenStack's own rule
# list (or reflected with a delay) - a naive resync would lose it.
# ============================================================
print("\n=== Scenario B: re-running for a second new node doesn't clobber the first ===")
sg_before = ClusterState.get_security_group("SG_worker-99")
# The rule's target is some OTHER (peer) node's SG, matching how real dynamic
# rules are shaped - SGn(n).remotes only ever holds rules targeting a peer's
# SG (n == m connections are skipped entirely by SG_add_conn), never itself.
# Targeting sg_before itself here would be unrealistic AND self-defeating:
# SecurityGroup.__hash__ includes frozenset(self.remotes), so a rule stored
# inside the very SG it targets has a hash that shifts on every add/remove -
# not what this scenario is trying to isolate.
peer_sg = SecurityGroup(id="peer-id", name="SG_some-peer", project="default")
live_rule = Rule(target=peer_sg, traffic=Traffic(direction="ingress", port=443, protocol="tcp"))
sg_before.remotes.add(live_rule)
node_before = ClusterState.get_node("worker-99")

run_create_sg_per_node(
    [FakeNode("worker-99", "10.0.0.99"), FakeNode("worker-100", "10.0.0.100")],
    {"worker-99", "worker-100"},
)

check("worker-99's SecurityGroup object identity is unchanged (not replaced)",
      ClusterState.get_security_group("SG_worker-99") is sg_before)
check("worker-99's live/concurrent rule survived the re-run",
      live_rule in ClusterState.get_security_group("SG_worker-99").remotes)
check("worker-99's Node object identity is unchanged (not replaced)",
      ClusterState.get_node("worker-99") is node_before)

sg_100 = ClusterState.get_security_group("SG_worker-100")
check("the actually-new node (worker-100) still gets registered", sg_100 is not None)
check("worker-100's SG is a distinct object from worker-99's", sg_100 is not sg_before)


# ============================================================
# Scenario C: the kopf handler itself only calls create_sg_per_node() in PNS
# mode - PLS mode has no per-node SGs at all (SecurityGroupModulePLS keys SGs
# by labelset, not by node), so this must be a no-op there.
# ============================================================
print("\n=== Scenario C: handle_new_node is gated to PNS mode ===")
with mock.patch("sys.argv", ["main_operator.py", "--mode", "PNS"]):
    import main_operator

with mock.patch("main_operator.create_sg_per_node") as mock_create:
    main_operator.MODE = "PNS"
    main_operator.handle_new_node(name="worker-101")
    check("PNS mode: create_sg_per_node() IS called for a new node", mock_create.called)

    mock_create.reset_mock()
    main_operator.MODE = "PLS"
    main_operator.handle_new_node(name="worker-102")
    check("PLS mode: create_sg_per_node() is NOT called (no per-node SGs in PLS)", not mock_create.called)


report_and_exit()
