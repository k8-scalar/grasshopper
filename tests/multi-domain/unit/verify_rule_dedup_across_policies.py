"""
Verifies Rule's hash/eq contract stays consistent, and that two independent
policies/pods converging on the same (target, traffic) never both attempt to
create the identical OpenStack rule.

Found live: Rule.__hash__ used to include self.id, but Rule.__eq__ considers
two rules equal whenever (target, traffic) match regardless of id - a fresh
Rule (id=None) built for a second policy hashed to a different bucket than
an already-created Rule (real id) with the same target+traffic, so
`rule not in SG.remotes` returned a false "not found". The existing CIDR
dedup test (verify_cidr_conn_add_remove.py Scenario B) never caught this:
_bootstrap.py's generic MagicMock() stubbing returns a consistent id across
calls rather than a realistic per-call-unique one, so the None-vs-real-id
mismatch this bug depends on never actually occurred there. This test uses a
mock that assigns a unique id per created rule and rejects an actual
duplicate create the way real Neutron does, so it fails the way the live
cluster did if the hash/eq inconsistency regresses.

Run with: python verify_rule_dedup_across_policies.py
"""
import os
import unittest.mock as mock

import _bootstrap
from _bootstrap import check, report_and_exit

from classes import Node, SecurityGroup, CIDR, Traffic
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


def cidr_pol_dict(name, ns, sel, cidr, port=9093, protocol="TCP"):
    return {
        "metadata": {"name": name, "namespace": ns},
        "spec": {"podSelector": {"matchLabels": sel}, "ingress": [{"from": [{"ipBlock": {"cidr": cidr}}], "ports": [{"port": port, "protocol": protocol}]}]},
    }


# ============================================================
# Direct contract check: a fresh (id=None) Rule must hash/compare equal to an
# already-created (real id) Rule sharing the same (target, traffic) - this is
# exactly what `rule not in SG.remotes` (a set-membership check) relies on.
# ============================================================
print("=== Rule hash/eq contract ===")
from classes import Rule

target = CIDR("203.0.113.0/24")
traffic = Traffic(direction="ingress", port=9093, protocol="TCP")
created_rule = Rule(target, traffic, id="real-neutron-id-1")
fresh_rule = Rule(target, traffic)  # id=None, as freshly built by rule_from()

check("fresh and already-created rules with the same (target, traffic) compare equal", fresh_rule == created_rule)
check("...and therefore MUST hash equally (Python's hash/eq contract)", hash(fresh_rule) == hash(created_rule))
check("set-membership finds the already-created rule via a fresh lookup key", fresh_rule in {created_rule})


# ============================================================
# Live-shaped scenario: two independent policies (different selectors),
# same CIDR+port target, second pod lands on the SAME node as the first -
# the second SG_add_conn call must recognize the rule already exists and
# never call create_security_group_rule again.
# ============================================================
print("\n=== Two independent policies/pods sharing a CIDR target on the same node ===")
reset_all()

created_rules = []  # (security_group_id, direction, protocol, port, remote_ip_prefix)


def make_fake_neutron():
    neutron = mock.MagicMock()

    def create_security_group_rule(body):
        r = body["security_group_rule"]
        key = (r["security_group_id"], r["direction"], r["protocol"], r["port_range_min"], r.get("remote_ip_prefix"))
        if key in created_rules:
            raise Exception(f"Security group rule already exists (simulated Neutron Conflict) for {key}")
        created_rules.append(key)
        return {"security_group_rule": {"id": f"rule-{len(created_rules)}"}}

    neutron.create_security_group_rule.side_effect = create_security_group_rule
    return neutron


fake_neutron = make_fake_neutron()
with mock.patch.object(OpenStackClient, "for_project", return_value=mock.MagicMock(get_neutron=lambda: fake_neutron)):
    wd = WatchDog(PNS_scenario=True)
    ClusterState.add_node(Node("shared-node", project="default", internal_ip="10.0.0.5"))
    ClusterState.add_security_group(SecurityGroup(id="sg-shared", name="SG_shared-node", project="default"))

    pol1 = Watcher.create_policy_from_policy_dict(cidr_pol_dict("policy-1", "ns", {"app": "server-1"}, "203.0.113.0/24"))
    pol2 = Watcher.create_policy_from_policy_dict(cidr_pol_dict("policy-2", "ns", {"app": "server-2"}, "203.0.113.0/24"))

    pod1 = Watcher.create_pod_from_pod_dict(pod_dict("server-1-pod", "ns", {"app": "server-1"}, "shared-node"))
    pod2 = Watcher.create_pod_from_pod_dict(pod_dict("server-2-pod", "ns", {"app": "server-2"}, "shared-node"))

    wd.handle_new_policy(pol1)
    wd.handle_new_policy(pol2)

    # pod1 arrives first - triggers the real, first-ever creation.
    try:
        wd.handle_new_pod(pod1)
        check("first pod's connection created without error", True)
    except Exception as e:
        check(f"first pod's connection created without error ({e})", False)

    # pod2 arrives second, on the SAME node, matching a DIFFERENT policy that
    # shares the exact same (CIDR, port) target - this is exactly the live
    # failure: a second, independent labelset needing the identical rule.
    try:
        wd.handle_new_pod(pod2)
        check("second pod (different policy, same target) does not raise", True)
    except Exception as e:
        check(f"second pod (different policy, same target) does not raise ({e})", False)

    check("create_security_group_rule was called exactly once for this rule shape (deduped correctly)", len(created_rules) == 1)
    check("SG.remotes has exactly one entry, not a duplicate", len(ClusterState.get_security_group("SG_shared-node").remotes) == 1)


report_and_exit()
