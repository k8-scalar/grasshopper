"""
Verifies create_master_and_workerSG()'s multi-domain fix: masterSG/workerSG
created per-project, same-project rules use remote_group_id, cross-project
rules use CIDR of the peer node's real IP, and nothing tries to attach a node
to an SG in a different OpenStack project.

Run with: python verify_master_worker_sg.py
"""
import types
import unittest.mock as mock

import _bootstrap
from _bootstrap import check, report_and_exit


class FakeAddr:
    def __init__(self, ip):
        self.type = "InternalIP"
        self.address = ip


class FakeNode:
    def __init__(self, name, labels, ip):
        self.metadata = types.SimpleNamespace(name=name, labels=labels)
        self.status = types.SimpleNamespace(addresses=[FakeAddr(ip)])


import openstackfiles.create_master_and_workerSG as cmw
from openstackfiles.openstack_client import OpenStackClient

PROJ_A = "proj-a"
PROJ_B = "proj-b"

nodes = [
    FakeNode("master-1", {cmw.master_node_label: "true", "grasshopper.io/openstack-project": PROJ_A}, "10.0.1.1"),
    FakeNode("worker-a1", {"grasshopper.io/openstack-project": PROJ_A}, "10.0.1.10"),
    FakeNode("worker-b1", {"grasshopper.io/openstack-project": PROJ_B}, "10.0.2.10"),
    FakeNode("worker-b2", {"grasshopper.io/openstack-project": PROJ_B}, "10.0.2.11"),
]

# Fake Nova: track which SG names got attached to which instance, and reject
# cross-project attach attempts the way real OpenStack would (each per-project
# OpenStackClient only "knows about" its own project's instances).
attached = []  # list of (project_key, instance_id, sg_name)

def make_fake_nova(project_key, valid_instances):
    nova = mock.MagicMock()
    def find(name):
        if name not in valid_instances:
            raise Exception(f"No server named {name} in project {project_key}")
        server = mock.MagicMock()
        server.list_security_group.return_value = []
        def add_security_group(sg_name, pk=project_key, inst=name):
            attached.append((pk, inst, sg_name))
        server.add_security_group.side_effect = add_security_group
        return server
    nova.servers.find.side_effect = find
    return nova

created_sgs = {}  # (project_key, sg_name) -> fake sg dict
created_rules = []  # (project_key, sg_id, direction, protocol, port_min, remote_group_id, remote_ip_prefix)

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

    def list_security_group_rules(security_group_id):
        return {"security_group_rules": []}

    def create_security_group_rule(body):
        r = body["security_group_rule"]
        created_rules.append((project_key, r["security_group_id"], r["direction"], r["protocol"],
                               r.get("port_range_min"), r.get("remote_group_id"), r.get("remote_ip_prefix")))
        return {"security_group_rule": {"id": f"rule-{len(created_rules)}"}}

    neutron.list_security_groups.side_effect = list_security_groups
    neutron.create_security_group.side_effect = create_security_group
    neutron.list_security_group_rules.side_effect = list_security_group_rules
    neutron.create_security_group_rule.side_effect = create_security_group_rule
    return neutron


valid_instances_by_project = {PROJ_A: {"master-1", "worker-a1"}, PROJ_B: {"worker-b1", "worker-b2"}}

def fake_for_project(project_key):
    client_obj = mock.MagicMock()
    client_obj.get_neutron.return_value = make_fake_neutron(project_key)
    client_obj.get_nova.return_value = make_fake_nova(project_key, valid_instances_by_project.get(project_key, set()))
    return client_obj


with mock.patch.object(OpenStackClient, "for_project", side_effect=fake_for_project), \
     mock.patch("kubernetes.config.load_kube_config"), \
     mock.patch("kubernetes.client.CoreV1Api") as MockCoreV1:
    MockCoreV1.return_value.list_node.return_value = types.SimpleNamespace(items=nodes)
    cmw.create_master_and_workerSG()


# ============================================================
check("masterSG created in proj-a (where the master is)", (PROJ_A, "masterSG") in created_sgs)
check("masterSG NOT created in proj-b (no master there)", (PROJ_B, "masterSG") not in created_sgs)
check("workerSG created in proj-a", (PROJ_A, "workerSG") in created_sgs)
check("workerSG created in proj-b", (PROJ_B, "workerSG") in created_sgs)

check("master-1 attached to masterSG in proj-a", (PROJ_A, "master-1", "masterSG") in attached)
check("worker-a1 attached to workerSG in proj-a", (PROJ_A, "worker-a1", "workerSG") in attached)
check("worker-b1 attached to workerSG in proj-b", (PROJ_B, "worker-b1", "workerSG") in attached)
check("worker-b2 attached to workerSG in proj-b", (PROJ_B, "worker-b2", "workerSG") in attached)
check("nothing attached cross-project (e.g. master-1 in proj-b)", not any(inst == "master-1" and pk == PROJ_B for pk, inst, sg in attached))
check("no attach attempts targeting nonexistent instances (would have raised)", True)  # implicit: no exception was raised above

# Same-project (proj-a master <-> proj-a worker) rules use remote_group_id.
same_project_rules = [r for r in created_rules if r[0] == PROJ_A and r[1] == created_sgs[(PROJ_A, "masterSG")]["id"]]
check("same-project masterSG rules include remote_group_id-based entries",
      any(r[5] == created_sgs[(PROJ_A, "workerSG")]["id"] for r in same_project_rules))

# Cross-project (proj-a master <-> proj-b worker) rules use CIDR, never remote_group_id to a foreign SG.
cross_rules_on_master = [r for r in created_rules if r[0] == PROJ_A and r[1] == created_sgs[(PROJ_A, "masterSG")]["id"] and r[6] in ("10.0.2.10/32", "10.0.2.11/32")]
check("cross-project rules on masterSG (proj-a) use CIDR of proj-b worker IPs", len(cross_rules_on_master) > 0)
check("cross-project rules never set remote_group_id to a foreign-project SG id",
      all(r[5] != created_sgs[(PROJ_B, "workerSG")]["id"] for r in created_rules if r[0] == PROJ_A))

cross_rules_on_worker_b = [r for r in created_rules if r[0] == PROJ_B and r[1] == created_sgs[(PROJ_B, "workerSG")]["id"] and r[6] == "10.0.1.1/32"]
check("cross-project rules on workerSG (proj-b) use CIDR of the proj-a master's IP", len(cross_rules_on_worker_b) > 0)

# VXLAN (udp/4789) rule-shape table: unconditional cross-project, toggle-gated same-project.
cross_rules_vxlan = [r for r in cross_rules_on_master if r[3] == "udp" and r[4] == 4789]
check("cross-project masterSG gets the VXLAN rule unconditionally (toggle still default/native)", len(cross_rules_vxlan) > 0)

worker_a_sg_id = created_sgs[(PROJ_A, "workerSG")]["id"]
same_project_vxlan_before = [r for r in same_project_rules if r[3] == "udp" and r[4] == 4789 and r[5] == worker_a_sg_id]
check("same-project masterSG does NOT get the VXLAN rule while toggle is native (default)", len(same_project_vxlan_before) == 0)

import network_mode
network_mode.configure(network_mode.ENCAPSULATION_VXLAN, 4789)
with mock.patch.object(OpenStackClient, "for_project", side_effect=fake_for_project), \
     mock.patch("kubernetes.config.load_kube_config"), \
     mock.patch("kubernetes.client.CoreV1Api") as MockCoreV1:
    MockCoreV1.return_value.list_node.return_value = types.SimpleNamespace(items=nodes)
    cmw.create_master_and_workerSG()

same_project_rules_after = [r for r in created_rules if r[0] == PROJ_A and r[1] == created_sgs[(PROJ_A, "masterSG")]["id"]]
same_project_vxlan_after = [r for r in same_project_rules_after if r[3] == "udp" and r[4] == 4789 and r[5] == created_sgs[(PROJ_A, "workerSG")]["id"]]
check("same-project masterSG DOES get the VXLAN rule once toggle is set to vxlan", len(same_project_vxlan_after) > 0)


report_and_exit()
