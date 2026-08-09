"""
Verifies ensure_typha_networkpolicy()'s own logic in main_operator.py:
- Skips (no create call) if no calico-typha pod is found anywhere.
- Skips (no create call) if a policy with its name already exists in Typha's
  namespace - idempotent, a pod restart never creates a duplicate.
- Otherwise creates a NetworkPolicy in Typha's actual (discovered, not
  hardcoded) namespace, targeting k8s-app=calico-typha, with one /32 ipBlock
  peer per currently-known node IP and no others - no guessed supernet.

Run with: python verify_ensure_typha_networkpolicy.py
"""
import types
import unittest.mock as mock

import _bootstrap
from _bootstrap import check, report_and_exit

import main_operator
from classes import Node


def fake_pod(namespace):
    return types.SimpleNamespace(metadata=types.SimpleNamespace(namespace=namespace))


def run(typha_pods, existing_policies, node_ips):
    created = []
    core = mock.MagicMock()
    core.list_pod_for_all_namespaces.return_value = types.SimpleNamespace(items=typha_pods)
    net = mock.MagicMock()
    net.list_namespaced_network_policy.return_value = types.SimpleNamespace(items=existing_policies)
    net.create_namespaced_network_policy.side_effect = lambda ns, policy: created.append((ns, policy))

    with mock.patch("kubernetes.client.CoreV1Api", return_value=core), \
         mock.patch("kubernetes.client.NetworkingV1Api", return_value=net), \
         mock.patch("cluster_state.ClusterState.get_nodes",
                    return_value=[Node(f"n{i}", internal_ip=ip) for i, ip in enumerate(node_ips)]):
        main_operator.ensure_typha_networkpolicy()

    return created, net


# No calico-typha pod anywhere - nothing to protect, skip.
created, net = run(typha_pods=[], existing_policies=[], node_ips=["10.0.0.1"])
check("no Typha pod -> no create attempt", not created)
check("no Typha pod -> doesn't even check for an existing policy", not net.list_namespaced_network_policy.called)

# Typha found, policy already exists - idempotent, skip.
created, net = run(
    typha_pods=[fake_pod("calico-system")],
    existing_policies=[mock.MagicMock()],
    node_ips=["10.0.0.1"],
)
check("policy already exists -> no create attempt", not created)

# Typha found in a non-default namespace, no existing policy, two known nodes.
created, net = run(
    typha_pods=[fake_pod("kube-system")],
    existing_policies=[],
    node_ips=["10.0.0.1", "10.0.0.2"],
)
check("exactly one policy created", len(created) == 1)
if created:
    namespace, policy = created[0]
    check("created in Typha's actual (discovered) namespace, not a hardcoded one", namespace == "kube-system")
    check("targets k8s-app=calico-typha", policy.spec.pod_selector.match_labels == {"k8s-app": "calico-typha"})
    peers = policy.spec.ingress[0]._from
    cidrs = sorted(p.ip_block.cidr for p in peers)
    check("one /32 ipBlock peer per known node IP, no more, no less", cidrs == ["10.0.0.1/32", "10.0.0.2/32"])
    check("ingress port is Typha's 5473/tcp", policy.spec.ingress[0].ports[0].port == 5473
          and policy.spec.ingress[0].ports[0].protocol == "TCP")

# No known node IPs yet - nothing to scope the policy to, skip rather than
# create an ipBlock-less (or wildcard) rule.
created, net = run(typha_pods=[fake_pod("calico-system")], existing_policies=[], node_ips=[])
check("no known node IPs -> no create attempt", not created)

report_and_exit()
