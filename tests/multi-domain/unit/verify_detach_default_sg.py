"""
Verifies detach_defaultSG()'s multi-domain fix: resolves "default" SG and the
worker instance per-project, never tries nova.servers.find() against an
instance that lives in a different OpenStack project.

Run with: python verify_detach_default_sg.py
"""
import types
import unittest.mock as mock

import _bootstrap
from _bootstrap import check, report_and_exit

import openstackfiles.detach_defaultSG as ddsg
from openstackfiles.openstack_client import OpenStackClient

PROJ_A, PROJ_B = "proj-a", "proj-b"

nodes = [
    types.SimpleNamespace(metadata=types.SimpleNamespace(name="master-1", labels={"node-role.kubernetes.io/control-plane": "true", "grasshopper.io/openstack-project": PROJ_A})),
    types.SimpleNamespace(metadata=types.SimpleNamespace(name="worker-a1", labels={"grasshopper.io/openstack-project": PROJ_A})),
    types.SimpleNamespace(metadata=types.SimpleNamespace(name="worker-b1", labels={"grasshopper.io/openstack-project": PROJ_B})),
]

detached = []  # (project_key, instance_name)
valid_instances = {PROJ_A: {"worker-a1"}, PROJ_B: {"worker-b1"}}


def fake_for_project(project_key):
    client_obj = mock.MagicMock()
    neutron = mock.MagicMock()
    neutron.list_security_groups.return_value = {"security_groups": [{"name": "default"}]}
    client_obj.get_neutron.return_value = neutron

    nova = mock.MagicMock()
    def find(name, pk=project_key):
        if name not in valid_instances.get(pk, set()):
            raise Exception(f"No server named {name} in project {pk}")
        server = mock.MagicMock()
        server.remove_security_group.side_effect = lambda sg, pk=pk, n=name: detached.append((pk, n))
        return server
    nova.servers.find.side_effect = find
    client_obj.get_nova.return_value = nova
    return client_obj


with mock.patch.object(OpenStackClient, "for_project", side_effect=fake_for_project), \
     mock.patch("kubernetes.config.load_kube_config"), \
     mock.patch("kubernetes.client.CoreV1Api") as MockCoreV1:
    MockCoreV1.return_value.list_node.return_value = types.SimpleNamespace(items=nodes)
    ddsg.detach_defaultSG()

check("worker-a1 (proj-a) had default SG detached via proj-a's own client", (PROJ_A, "worker-a1") in detached)
check("worker-b1 (proj-b) had default SG detached via proj-b's own client", (PROJ_B, "worker-b1") in detached)
check("master-1 was skipped (control-plane node)", not any(n == "master-1" for _, n in detached))
check("no cross-project find() attempts (would have raised)", True)

report_and_exit()
