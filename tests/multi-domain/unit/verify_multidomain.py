"""
Verifies the core multi-domain feature: OpenStackClient's per-project
registry (with single-project backward compatibility), rule_from()'s
rule-shape table (same-project native / same-project vxlan / cross-project),
the CIDR-target fix in add_rule_to_remotes, and that a rule always resolves
its OpenStack client from the SG's own project.

Run with: python verify_multidomain.py
"""
import json
import unittest.mock as mock

import _bootstrap
from _bootstrap import check, report_and_exit

from classes import Node, SecurityGroup, Rule, Traffic, CIDR, Policy, LabelSet
from cluster_state import ClusterState
import network_mode
from openstackfiles.openstack_client import OpenStackClient
from security_group_module import SecurityGroupModulePNS, SecurityGroupModule

import os


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
    network_mode.intra_project_encapsulation = network_mode.ENCAPSULATION_NATIVE
    network_mode.vxlan_port = 4789
    for key in ("OS_PROJECTS_JSON", "OS_AUTH_URL", "OS_APPLICATION_CREDENTIAL_ID",
                "OS_APPLICATION_CREDENTIAL_SECRET", "OS_NEUTRON_ENDPOINT", "OS_NOVA_ENDPOINT"):
        os.environ.pop(key, None)


def make_policy(sel_labels, allow_labels, port=80, direction="ingress"):
    return Policy(
        "pol", LabelSet(sel_labels, {"kubernetes.io/metadata.name": "default"}),
        [(LabelSet(allow_labels, {"kubernetes.io/metadata.name": "default"}), Traffic(direction, port, "tcp"))],
        namespace="default",
    )


# ============================================================
# Scenario A: OpenStackClient.for_project - backward-compat fallback
# ============================================================
print("\n=== Scenario A: OpenStackClient backward-compat (no OS_PROJECTS_JSON) ===")
reset_all()
os.environ["OS_AUTH_URL"] = "https://legacy.example.com:5000"
os.environ["OS_APPLICATION_CREDENTIAL_ID"] = "legacy-id"
os.environ["OS_APPLICATION_CREDENTIAL_SECRET"] = "legacy-secret"

default_client = OpenStackClient()  # no-arg, legacy call style
check("no-arg OpenStackClient() resolves to 'default' project", default_client.project_key == "default")
check("known_project_keys() == ['default'] with no OS_PROJECTS_JSON", OpenStackClient.known_project_keys() == ["default"])
check("for_project('default') returns the SAME cached instance", OpenStackClient.for_project("default") is default_client)


# ============================================================
# Scenario B: OpenStackClient.for_project - real multi-project config
# ============================================================
print("\n=== Scenario B: OpenStackClient multi-project (OS_PROJECTS_JSON) ===")
reset_all()
os.environ["OS_PROJECTS_JSON"] = json.dumps([
    {"key": "proj-a", "auth_url": "https://a.example.com:5000",
     "application_credential_id": "a-id", "application_credential_secret": "a-secret",
     "neutron_endpoint": "https://a.example.com:9696", "nova_endpoint": "https://a.example.com:8774/v2.1"},
    {"key": "proj-b", "auth_url": "https://b.example.com:5000",
     "application_credential_id": "b-id", "application_credential_secret": "b-secret",
     "neutron_endpoint": "https://b.example.com:9696", "nova_endpoint": "https://b.example.com:8774/v2.1"},
])

client_a = OpenStackClient.for_project("proj-a")
client_b = OpenStackClient.for_project("proj-b")
# "default" is NOT synthesized into known_project_keys() unless OS_PROJECTS_JSON
# itself defines it - the flat-env-var fallback is lazy, only materialized if
# something actually asks for_project("default")/OpenStackClient() explicitly.
# This matters: code that loops over "every configured project" (e.g.
# initialize_security_groups) must never try to init a phantom "default" with
# no real credentials just because it exists as a key.
check("known_project_keys() is exactly the two real projects, no phantom 'default'",
      set(OpenStackClient.known_project_keys()) == {"proj-a", "proj-b"})
check("proj-a and proj-b get distinct OpenStackClient instances", client_a is not client_b)
check("proj-a's neutron session differs from proj-b's", client_a.get_neutron() is not client_b.get_neutron())
check("for_project('proj-a') is stable/cached across calls", OpenStackClient.for_project("proj-a") is client_a)

try:
    OpenStackClient.for_project("does-not-exist")
    check("for_project() on unknown key raises", False)
except Exception:
    check("for_project() on unknown key raises", True)


# ============================================================
# Scenario C: rule_from rule-shape table (the 3 rows from the design doc)
# ============================================================
print("\n=== Scenario C: rule_from rule-shape table ===")
reset_all()

n_same = Node("n-same", project="proj-a", internal_ip="10.0.1.10")
m_same = Node("m-same", project="proj-a", internal_ip="10.0.1.11")
m_cross = Node("m-cross", project="proj-b", internal_ip="10.0.2.20")
for node in (n_same, m_same, m_cross):
    ClusterState.add_node(node)

sg_m_same = SecurityGroup(id="sg-m-same-id", name="SG_m-same", project="proj-a")
sg_m_cross = SecurityGroup(id="sg-m-cross-id", name="SG_m-cross", project="proj-b")
ClusterState.add_security_group(sg_m_same)
ClusterState.add_security_group(sg_m_cross)

pol = make_policy({"app": "a"}, {"app": "b"}, port=80)

# Row 1: same project, native (default) -> SG reference, real port unchanged.
rule1 = SecurityGroupModulePNS.rule_from(pol, n_same, m_same)
check("Row1 (same-project, native): target is the peer's SG", rule1.target is sg_m_same)
check("Row1 (same-project, native): traffic port is the policy's real port (80)", rule1.traffic.port == 80)
check("Row1 (same-project, native): protocol unchanged (tcp)", rule1.traffic.protocol == "tcp")

# Row 2: same project, intra-project VXLAN toggle ON -> SG reference (unchanged), VXLAN port.
network_mode.configure(network_mode.ENCAPSULATION_VXLAN, 4789)
rule2 = SecurityGroupModulePNS.rule_from(pol, n_same, m_same)
check("Row2 (same-project, vxlan toggle): target still the peer's SG", rule2.target is sg_m_same)
check("Row2 (same-project, vxlan toggle): traffic port becomes VXLAN port (4789)", rule2.traffic.port == 4789)
check("Row2 (same-project, vxlan toggle): protocol becomes udp", rule2.traffic.protocol == "udp")
network_mode.configure(network_mode.ENCAPSULATION_NATIVE, 4789)  # reset toggle

# Row 3: different projects -> CIDR of peer's node IP, VXLAN port, REGARDLESS of toggle.
rule3 = SecurityGroupModulePNS.rule_from(pol, n_same, m_cross)
check("Row3 (cross-project): target is a CIDR", isinstance(rule3.target, CIDR))
check("Row3 (cross-project): CIDR is peer's internal_ip/32", rule3.target.cidr == "10.0.2.20/32")
check("Row3 (cross-project): traffic port is VXLAN port even with toggle off", rule3.traffic.port == 4789)
check("Row3 (cross-project): protocol becomes udp", rule3.traffic.protocol == "udp")

# Cross-project peer with no known internal_ip -> should raise, not silently build a bad rule.
m_cross_no_ip = Node("m-cross-no-ip", project="proj-b", internal_ip=None)
ClusterState.add_node(m_cross_no_ip)
try:
    SecurityGroupModulePNS.rule_from(pol, n_same, m_cross_no_ip)
    check("cross-project peer with no internal_ip raises instead of building a bad rule", False)
except Exception:
    check("cross-project peer with no internal_ip raises instead of building a bad rule", True)

# Ad hoc (disposable) Node instances without project/ip must still resolve via
# ClusterState.get_node() to the canonical instance's real project/ip.
n_adhoc = Node("n-same")   # no project/internal_ip passed - defaults only
m_adhoc = Node("m-cross")  # same name as the canonical cross-project node above
rule_adhoc = SecurityGroupModulePNS.rule_from(pol, n_adhoc, m_adhoc)
check("ad hoc Node instances resolve project via ClusterState.get_node(), not their own defaults",
      isinstance(rule_adhoc.target, CIDR) and rule_adhoc.target.cidr == "10.0.2.20/32")


# ============================================================
# Scenario D: CIDR-target bug fix in add_rule_to_remotes
# ============================================================
print("\n=== Scenario D: add_rule_to_remotes CIDR-target fix ===")
reset_all()
os.environ["OS_AUTH_URL"] = "https://legacy.example.com:5000"

sg = SecurityGroup(id="sg-id", name="SG_n1", project="default")
mock_neutron = mock.MagicMock()
mock_neutron.create_security_group_rule.return_value = {"security_group_rule": {"id": "rule-id-1"}}

with mock.patch.object(OpenStackClient, "for_project", return_value=mock.MagicMock(get_neutron=lambda: mock_neutron)):
    cidr_rule = Rule(CIDR("10.0.2.20/32"), Traffic("ingress", 4789, "udp"))
    try:
        SecurityGroupModule.add_rule_to_remotes(sg, cidr_rule)
        check("add_rule_to_remotes with a CIDR target does not raise AttributeError", True)
    except AttributeError as e:
        check(f"add_rule_to_remotes with a CIDR target does not raise AttributeError (got: {e})", False)

    call_kwargs = mock_neutron.create_security_group_rule.call_args[0][0]["security_group_rule"]
    check("CIDR-target rule uses remote_ip_prefix", call_kwargs.get("remote_ip_prefix") == "10.0.2.20/32")
    check("CIDR-target rule does NOT set remote_group_id", "remote_group_id" not in call_kwargs)

# Sanity: SG-target (today's unchanged path) still uses remote_group_id.
reset_all()
os.environ["OS_AUTH_URL"] = "https://legacy.example.com:5000"
mock_neutron2 = mock.MagicMock()
mock_neutron2.create_security_group_rule.return_value = {"security_group_rule": {"id": "rule-id-2"}}
target_sg = SecurityGroup(id="target-sg-id", name="SG_m1", project="default")
sg2 = SecurityGroup(id="sg2-id", name="SG_n2", project="default")
with mock.patch.object(OpenStackClient, "for_project", return_value=mock.MagicMock(get_neutron=lambda: mock_neutron2)):
    sg_rule = Rule(target_sg, Traffic("ingress", 80, "tcp"))
    SecurityGroupModule.add_rule_to_remotes(sg2, sg_rule)
    call_kwargs2 = mock_neutron2.create_security_group_rule.call_args[0][0]["security_group_rule"]
    check("SG-target rule still uses remote_group_id (unchanged path)", call_kwargs2.get("remote_group_id") == "target-sg-id")
    check("SG-target rule does NOT set remote_ip_prefix", "remote_ip_prefix" not in call_kwargs2)


# ============================================================
# Scenario E: project-aware client resolution
# ============================================================
print("\n=== Scenario E: add_rule_to_remotes resolves the SG's OWN project's client ===")
reset_all()
os.environ["OS_PROJECTS_JSON"] = json.dumps([
    {"key": "proj-a", "auth_url": "https://a.example.com:5000",
     "application_credential_id": "a-id", "application_credential_secret": "a-secret",
     "neutron_endpoint": "https://a.example.com:9696", "nova_endpoint": "https://a.example.com:8774/v2.1"},
    {"key": "proj-b", "auth_url": "https://b.example.com:5000",
     "application_credential_id": "b-id", "application_credential_secret": "b-secret",
     "neutron_endpoint": "https://b.example.com:9696", "nova_endpoint": "https://b.example.com:8774/v2.1"},
])
client_a = OpenStackClient.for_project("proj-a")
client_b = OpenStackClient.for_project("proj-b")
client_a.get_neutron().create_security_group_rule.return_value = {"security_group_rule": {"id": "r-a"}}
client_b.get_neutron().create_security_group_rule.return_value = {"security_group_rule": {"id": "r-b"}}

sg_in_a = SecurityGroup(id="sg-a-id", name="SG_x", project="proj-a")
cidr_rule = Rule(CIDR("10.0.2.20/32"), Traffic("ingress", 4789, "udp"))
SecurityGroupModule.add_rule_to_remotes(sg_in_a, cidr_rule)

check("rule for a proj-a SG was created via proj-a's neutron client", client_a.get_neutron().create_security_group_rule.called)
check("rule for a proj-a SG was NOT created via proj-b's neutron client", not client_b.get_neutron().create_security_group_rule.called)


report_and_exit()
