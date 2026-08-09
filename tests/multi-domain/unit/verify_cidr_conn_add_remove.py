"""
Verifies SG_add_conn/SG_remove_conn (security_group_module.py) and
other_policy_provides_traffic (helpers.py) correctly handle a policy whose
peer is a CIDR (ipBlock) - the case found live via the Typha ingress policy
(allow from 172.22.0.0/16). Before this fix: SG_add_conn/SG_remove_conn
crashed on `m.name` (m is None for a CIDR peer - there's no single matched
Node), and SG_remove_conn's blanket `if not isinstance(..., CIDR)` guard
meant a CIDR-based rule was never actually removed at all.

Run with: python verify_cidr_conn_add_remove.py
"""
import os

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


def cidr_pol_dict(name, ns, sel, cidr, port=5473, protocol="TCP"):
    return {
        "metadata": {"name": name, "namespace": ns},
        "spec": {"podSelector": {"matchLabels": sel}, "ingress": [{"from": [{"ipBlock": {"cidr": cidr}}], "ports": [{"port": port, "protocol": protocol}]}]},
    }


def remotes_of(sg_name):
    return ClusterState.get_security_group(sg_name).remotes


# ============================================================
# Scenario A: add + remove a CIDR-peer policy - must not crash, must add
# and then actually remove the rule (not silently no-op the removal).
# ============================================================
print("=== Scenario A: add then remove a CIDR-peer policy ===")
reset_all()
wd = WatchDog(PNS_scenario=True)
n_typha = Node("n-typha", project="default", internal_ip="10.0.0.1")
ClusterState.add_node(n_typha)
ClusterState.add_security_group(SecurityGroup(id="sg-typha", name="SG_n-typha", project="default"))

pol = Watcher.create_policy_from_policy_dict(cidr_pol_dict("allow-typha-ingress", "calico-system", {"k8s-app": "calico-typha"}, "172.22.0.0/16"))
pod_typha = Watcher.create_pod_from_pod_dict(pod_dict("calico-typha-1", "calico-system", {"k8s-app": "calico-typha"}, "n-typha"))

wd.handle_new_pod(pod_typha)
try:
    wd.handle_new_policy(pol)
    check("handle_new_policy with a CIDR peer does not crash", True)
except AttributeError as e:
    check(f"handle_new_policy with a CIDR peer does not crash ({e})", False)

check("rule added to SG_n-typha for the CIDR peer", len(remotes_of("SG_n-typha")) == 1)

try:
    wd.handle_removed_policy(pol)
    check("handle_removed_policy with a CIDR peer does not crash", True)
except AttributeError as e:
    check(f"handle_removed_policy with a CIDR peer does not crash ({e})", False)

check("rule actually removed from SG_n-typha (not a silent no-op)", len(remotes_of("SG_n-typha")) == 0)


# ============================================================
# Scenario B: a second, independent CIDR-peer policy with the SAME CIDR
# and traffic must keep the rule alive when only one of the two is removed.
# ============================================================
print("\n=== Scenario B: two policies sharing the same CIDR target - must not remove early ===")
reset_all()
wd = WatchDog(PNS_scenario=True)
ClusterState.add_node(Node("n-typha", project="default", internal_ip="10.0.0.1"))
ClusterState.add_security_group(SecurityGroup(id="sg-typha", name="SG_n-typha", project="default"))

pol1 = Watcher.create_policy_from_policy_dict(cidr_pol_dict("allow-typha-ingress-1", "calico-system", {"k8s-app": "calico-typha"}, "172.22.0.0/16"))
pol2 = Watcher.create_policy_from_policy_dict(cidr_pol_dict("allow-typha-ingress-2", "calico-system", {"app.kubernetes.io/name": "calico-typha"}, "172.22.0.0/16"))
pod_typha = Watcher.create_pod_from_pod_dict(pod_dict("calico-typha-1", "calico-system", {"k8s-app": "calico-typha", "app.kubernetes.io/name": "calico-typha"}, "n-typha"))

wd.handle_new_pod(pod_typha)
wd.handle_new_policy(pol1)
wd.handle_new_policy(pol2)
check("rule exists after both CIDR policies applied", len(remotes_of("SG_n-typha")) == 1)

wd.handle_removed_policy(pol1)
check("rule SURVIVES removal of pol1 because pol2 shares the same CIDR target", len(remotes_of("SG_n-typha")) == 1)

wd.handle_removed_policy(pol2)
check("rule removed once the LAST CIDR policy needing it is removed", len(remotes_of("SG_n-typha")) == 0)


report_and_exit()
