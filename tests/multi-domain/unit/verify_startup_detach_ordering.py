"""
Verifies main_operator.py's startup() ordering: in PNS mode, it processes
every already-existing NetworkPolicy before calling detach_defaultSG() - not
after, and not skipped. Detaching "default" from workers before whatever
policies already exist (e.g. a Typha ipBlock policy, applied by
Deployment/install_grasshopper.sh before this pod ever starts - see
Deployment/networkpolicies/) have been processed leaves a real ingress gap -
confirmed live, see README_v2.md.

Also verifies startup() does NOT detach at all in PLS mode, since multi-domain/
this detach flow assumes PNS (see the Scope section of README_v2.md).

Run with: python verify_startup_detach_ordering.py
"""
import sys
import types
import unittest.mock as mock

import _bootstrap
from _bootstrap import check, report_and_exit

calls = []


class FakeResponse:
    def __init__(self, items):
        self._items = items

    def read(self):
        import json
        return json.dumps({"items": self._items}).encode()


def make_fake_core_v1():
    core = mock.MagicMock()
    core.list_node.return_value = types.SimpleNamespace(items=[])
    return core


def make_fake_networking_v1(existing_policies):
    net = mock.MagicMock()
    net.list_network_policy_for_all_namespaces.return_value = FakeResponse(existing_policies)
    return net


existing_policy_dict = {
    "metadata": {"name": "allow-typha-ingress-from-felix", "namespace": "calico-system"},
    "spec": {"podSelector": {"matchLabels": {"k8s-app": "calico-typha"}}, "ingress": [], "egress": []},
}

with mock.patch("kubernetes.config.load_kube_config"), \
     mock.patch("kubernetes.client.CoreV1Api", side_effect=lambda: make_fake_core_v1()), \
     mock.patch("kubernetes.client.NetworkingV1Api", side_effect=lambda: make_fake_networking_v1([existing_policy_dict])), \
     mock.patch("openstackfiles.create_sg_per_node.create_sg_per_node"), \
     mock.patch("openstackfiles.detach_defaultSG.detach_defaultSG", side_effect=lambda: calls.append("detach")), \
     mock.patch("cluster_state.ClusterState.initialize_light"), \
     mock.patch("cluster_state.ClusterState.initialize_security_groups"), \
     mock.patch("operator_code.watcher_operator.Watcher.create_policy_from_policy_dict",
                side_effect=lambda item: calls.append(f"process:{item['metadata']['name']}") or mock.MagicMock()), \
     mock.patch("watchdog.WatchDog.handle_new_policy", side_effect=lambda pol: None), \
     mock.patch("operator_code.watcher_operator.Watcher.__init__", return_value=None), \
     mock.patch("watchdog.WatchDog.__init__", return_value=None), \
     mock.patch("sys.argv", ["main_operator.py", "--mode", "PNS"]):
    import main_operator
    main_operator.startup()

check("existing policy was processed", "process:allow-typha-ingress-from-felix" in calls)
check("detach_defaultSG ran", "detach" in calls)
check("policy processed before detach", calls.index("process:allow-typha-ingress-from-felix") < calls.index("detach"))

# PLS mode: startup() must not touch detach_defaultSG at all.
calls.clear()
with mock.patch("kubernetes.config.load_kube_config"), \
     mock.patch("kubernetes.client.CoreV1Api", side_effect=lambda: make_fake_core_v1()), \
     mock.patch("kubernetes.client.NetworkingV1Api", side_effect=lambda: make_fake_networking_v1([existing_policy_dict])), \
     mock.patch("openstackfiles.detach_defaultSG.detach_defaultSG", side_effect=lambda: calls.append("detach")), \
     mock.patch("cluster_state.ClusterState.initialize_light"), \
     mock.patch("operator_code.watcher_operator.Watcher.__init__", return_value=None), \
     mock.patch("watchdog.WatchDog.__init__", return_value=None), \
     mock.patch("sys.argv", ["main_operator.py", "--mode", "PLS"]):
    main_operator.startup()

check("PLS mode never calls detach_defaultSG", "detach" not in calls)

report_and_exit()
