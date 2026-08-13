"""
Verifies the OpenStack API call timeout fix (openstackfiles/openstack_client.py)
- the root-cause fix for the reconciliation-loop fragility found this session:
without a timeout, a single slow/unresponsive Neutron/Nova call blocks
forever, holding whatever labelset lock(s) it needs, and for the
reconciliation loop specifically, permanently and silently disabling all
future ticks (reconcile_once() would simply never return, so the loop never
reaches its own next time.sleep()).

Covers:
- OpenStackClient._initialize() passes the configured timeout to the
  keystoneauth1 Session every Neutron/Nova call goes through - not to the
  neutron/nova clients independently, since both share that one session.
- The default (no configure() call) matches DEFAULT_REQUEST_TIMEOUT_SECONDS.
- configure() changes the timeout used by subsequently-constructed clients.
- main_operator.py's startup() wires --openstack-timeout-seconds through to
  openstack_client.configure() before anything could construct a client.

Run with: python verify_openstack_timeout.py
"""
import types
import unittest.mock as mock

import _bootstrap
from _bootstrap import check, report_and_exit

import keystoneauth1.session as ks_session
import openstackfiles.openstack_client as openstack_client
from openstackfiles.openstack_client import OpenStackClient

import os


def reset_all():
    OpenStackClient._instances.clear()
    OpenStackClient._credentials_by_key = None
    openstack_client.configure(openstack_client.DEFAULT_REQUEST_TIMEOUT_SECONDS)
    ks_session.Session.reset_mock()
    for key in ("OS_PROJECTS_JSON", "OS_AUTH_URL", "OS_APPLICATION_CREDENTIAL_ID",
                "OS_APPLICATION_CREDENTIAL_SECRET", "OS_NEUTRON_ENDPOINT", "OS_NOVA_ENDPOINT"):
        os.environ.pop(key, None)
    os.environ["OS_AUTH_URL"] = "https://example.com:5000"
    os.environ["OS_APPLICATION_CREDENTIAL_ID"] = "id"
    os.environ["OS_APPLICATION_CREDENTIAL_SECRET"] = "secret"


# ============================================================
# Scenario A: default timeout is used when configure() was never called.
# ============================================================
print("=== Scenario A: default timeout applied to the shared session ===")
reset_all()
OpenStackClient.for_project("default")

check("Session was constructed", ks_session.Session.called)
check(f"default timeout ({openstack_client.DEFAULT_REQUEST_TIMEOUT_SECONDS}s) passed to the session",
      ks_session.Session.call_args.kwargs.get("timeout") == openstack_client.DEFAULT_REQUEST_TIMEOUT_SECONDS)


# ============================================================
# Scenario B: configure() changes the timeout used by the NEXT client built -
# this is what --openstack-timeout-seconds ultimately controls.
# ============================================================
print("\n=== Scenario B: configure() overrides the timeout for new clients ===")
reset_all()
openstack_client.configure(15)
OpenStackClient.for_project("default")

check("overridden timeout (15s) passed to the session, not the default",
      ks_session.Session.call_args.kwargs.get("timeout") == 15)

# An already-constructed (cached) client is untouched by a later configure()
# call - only clients built AFTER the change pick it up. Documenting this,
# not just asserting it, since it's a real ordering constraint: configure()
# must run before startup() constructs anything, not just at some point.
ks_session.Session.reset_mock()
OpenStackClient.for_project("default")  # same project key - returns the cached instance
check("re-requesting the same (cached) project does not reconstruct the session",
      not ks_session.Session.called)


# ============================================================
# Scenario C: main_operator.py's startup() wires the CLI flag through to
# openstack_client.configure() before anything could construct a client.
# ============================================================
print("\n=== Scenario C: startup() wires --openstack-timeout-seconds through ===")
reset_all()


def make_fake_core_v1():
    core = mock.MagicMock()
    core.list_node.return_value = types.SimpleNamespace(items=[])
    return core


with mock.patch("kubernetes.config.load_kube_config"), \
     mock.patch("kubernetes.client.CoreV1Api", side_effect=lambda: make_fake_core_v1()), \
     mock.patch("openstackfiles.create_sg_per_node.create_sg_per_node"), \
     mock.patch("openstackfiles.detach_defaultSG.detach_defaultSG"), \
     mock.patch("cluster_state.ClusterState.initialize_light"), \
     mock.patch("cluster_state.ClusterState.initialize_security_groups"), \
     mock.patch("operator_code.watcher_operator.Watcher.__init__", return_value=None), \
     mock.patch("watchdog.WatchDog.__init__", return_value=None), \
     mock.patch("main_operator.ensure_typha_networkpolicy"), \
     mock.patch("main_operator.process_existing_network_policies"), \
     mock.patch("threading.Thread"), \
     mock.patch("sys.argv", ["main_operator.py", "--mode", "PNS", "--openstack-timeout-seconds", "45"]):
    import main_operator
    main_operator.startup()

check("startup() propagated --openstack-timeout-seconds to openstack_client",
      openstack_client.request_timeout_seconds == 45)

# And confirm that value is what a client built afterward actually gets.
OpenStackClient.for_project("default")
check("a client built after startup() gets the CLI-configured timeout (45s)",
      ks_session.Session.call_args.kwargs.get("timeout") == 45)


report_and_exit()
