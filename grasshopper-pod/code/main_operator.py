import kopf
import argparse
import json
import os
from cluster_state import ClusterState
from openstackfiles.create_sg_per_node import create_sg_per_node
from openstackfiles.detach_defaultSG import detach_defaultSG
from kubernetes import client, config
from operator_code.watcher_operator import Watcher
from watchdog import WatchDog
import network_mode
import openstackfiles.openstack_client as openstack_client
import logging
import time
import pandas as pd
import csv
import threading


MODE = None
watcher = None
watchdog = None

# kopf settings.
MAX_WORKERS = 20
DELAY = 2

# Throttling handlers (remove_policy)
WAIT_TIME = 2
last_run_time = 0
remove_handler_lock = threading.Lock()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

logger = logging.getLogger(__file__)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['PNS', 'PLS'], required=True)
    parser.add_argument(
        '--intra-project-encapsulation',
        choices=[network_mode.ENCAPSULATION_NATIVE, network_mode.ENCAPSULATION_VXLAN],
        default=network_mode.ENCAPSULATION_NATIVE,
        help="Whether same-OpenStack-project connections are native-routed (default) "
             "or also VXLAN-encapsulated by Calico. Cross-project connections always "
             "require VXLAN regardless of this setting - only relevant to PNS mode.",
    )
    parser.add_argument(
        '--vxlan-port', type=int, default=network_mode.vxlan_port,
        help="VXLAN encapsulation UDP port (Calico's default is 4789).",
    )
    parser.add_argument(
        '--reconcile-interval-seconds', type=int, default=60,
        help="How often the batch reconciliation loop re-syncs pods against "
             "the event-driven handlers' state, catching anything they "
             "missed. 0 disables it.",
    )
    parser.add_argument(
        '--openstack-timeout-seconds', type=int, default=openstack_client.DEFAULT_REQUEST_TIMEOUT_SECONDS,
        help="Timeout for every Neutron/Nova API call. Without one, a single "
             "slow/unresponsive OpenStack call blocks forever, holding "
             "whatever labelset lock(s) it needs - and for the reconciliation "
             "loop specifically, permanently and silently disabling all "
             "future ticks, since reconcile_once() would simply never return.",
    )
    return parser.parse_args()

def initialize_cluster_configuration():
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
        config.load_incluster_config()
    else:
        config.load_kube_config()

def process_existing_network_policies():
    """
    Synchronously processes every NetworkPolicy that already exists at pod
    startup, so that by the time detach_defaultSG() runs (right after this,
    still inside startup()) every policy the operator needs to have reacted
    to (e.g. a Typha ipBlock policy - see README_v2.md) already has its
    dynamic per-node rule created. Reprocessing the same policy later via the
    @kopf.on.resume handler below is harmless - WatchDog.handle_new_policy
    already no-ops if the policy is already in ClusterState.

    Uses the raw, unparsed API response (_preload_content=False) rather than
    the typed client's .to_dict(): the typed client's dict form uses
    snake_case field names (pod_selector, not podSelector), which
    create_policy_from_policy_dict - written for kopf's raw camelCase JSON
    body - wouldn't recognize.
    """
    resp = client.NetworkingV1Api().list_network_policy_for_all_namespaces(_preload_content=False)
    for item in json.loads(resp.read())["items"]:
        policy = Watcher.create_policy_from_policy_dict(item)
        watchdog.handle_new_policy(policy)

def startup():
    global MODE, watcher, watchdog
    args = parse_args()
    MODE = args.mode
    network_mode.configure(args.intra_project_encapsulation, args.vxlan_port)
    # Must run before anything constructs an OpenStackClient (every project's
    # client is created lazily, on first use, from wherever that happens to
    # be - create_sg_per_node() below is typically the first).
    openstack_client.configure(args.openstack_timeout_seconds)

    print(f"🚀 Starting Kopf operator in mode: {MODE}, watching all namespaces. "
          f"intra-project encapsulation: {network_mode.intra_project_encapsulation}.")

    # Each OpenStackClient is now created lazily per-project (via for_project())
    # by whatever code first needs that project's Neutron/Nova session - no
    # eager single "default" warm-up here, since assuming a "default" project
    # always exists is exactly what multi-domain support removes.

    # Initializing cluster configuration.
    initialize_cluster_configuration()

    # Initializing Cluster State.
    ClusterState().initialize_light(PNS_scenario=(MODE == "PNS"))

    # If mode is PNS, create a sg for every node.
    if MODE == "PNS":
        create_sg_per_node(delete_existing_rules=True)
        # initialize_light() (above) already listed existing SGs into
        # ClusterState, but create_sg_per_node() may have just created brand
        # new ones (e.g. first run against a fresh node) - re-list so every
        # per-node SG is registered before any policy/pod event tries to look
        # it up via SecurityGroupModulePNS.SGn(), which would otherwise return
        # None for a freshly-created node's SG.
        ClusterState.initialize_security_groups(PNS_scenario=True)

    # Create Watcher.
    watcher = Watcher(PNS_scenario=(MODE == "PNS"))
    watchdog = WatchDog(PNS_scenario=(MODE == "PNS"))

    if MODE == "PNS":
        # Bootstrap-critical NetworkPolicies (Typha's ingress, or whatever
        # else a given cluster's CNI needs) are the responsibility of
        # Deployment/install_grasshopper.sh, applied before this pod ever
        # starts - see Deployment/networkpolicies/ and README.md. Grasshopper
        # itself has no CNI-specific knowledge; it only needs to process
        # every already-existing NetworkPolicy before detaching "default"
        # from workers - detaching any earlier leaves a real ingress gap for
        # whatever traffic those policies were supposed to open (confirmed
        # live - see README_v2.md).
        process_existing_network_policies()
        detach_defaultSG()

    # Batch reconciliation is complementary to, not a replacement for, every
    # event-driven handler above - mode-agnostic (pod tracking matters in PLS
    # too), so this runs regardless of MODE. args.reconcile_interval_seconds
    # of 0 disables it entirely (e.g. for a test run that wants a completely
    # quiet log).
    if args.reconcile_interval_seconds > 0:
        threading.Thread(
            target=reconciliation_loop, args=(args.reconcile_interval_seconds,), daemon=True
        ).start()
        print(f"Batch reconciliation loop started, interval {args.reconcile_interval_seconds}s.")

@kopf.on.startup()
def startup_handler(settings: kopf.OperatorSettings, **kwargs):
    settings.execution.max_workers = MAX_WORKERS
    settings.posting.backoff = DELAY
    logger.info(f"Starting Operator with {MAX_WORKERS} workers.")
    startup()

# Handler for a worker/master node joining the cluster after Grasshopper has
# already started. Existing-at-startup nodes are already handled once, in
# full, by create_sg_per_node() inside startup() - deliberately no
# @kopf.on.resume here too, that would just redo the same idempotent work a
# second time for every node on every operator restart. PLS mode has no
# per-node SGs (SecurityGroupModulePLS keys SGs by labelset, not by node), so
# this is a no-op outside PNS mode.
@kopf.on.create('v1', 'nodes')
def handle_new_node(name, **kwargs):
    if MODE != "PNS":
        return
    print(f"New node joined the cluster: {name} - creating its per-node SG.")
    create_sg_per_node()

# ============================================================
# Batch reconciliation loop - a timing-based safety net that runs alongside
# (never instead of) the event-driven kopf handlers above. Those handlers
# react immediately to individual pod events, which is strictly better when
# they fire - this loop exists for when they don't: a handler that raised
# past its retries, or a watch stream gap. It periodically re-lists the
# cluster's actual current pods and replays the SAME batch handler functions
# (WatchDog.handle_new_pods_batch/handle_removed_pods_batch) for anything
# that's drifted - it does not duplicate their logic.
# ============================================================

def reconcile_pods_once():
    """
    Batch-reconciles ClusterState's tracked pods against the cluster's actual
    current pods in one pass: any pod that exists but isn't tracked (a missed
    create/field event) is handled as new; any tracked pod that no longer
    exists (a missed delete event) is handled as removed. Both go through
    WatchDog's batch methods (handle_new_pods_batch/handle_removed_pods_batch)
    - the whole point of a reconciliation pass is "here's everything that
    might have drifted, converge it," which is exactly the shape a batch
    computation wants: figure out the eventual (labelset, node) SG
    configuration for the WHOLE group in memory, then apply only the deltas
    once, rather than replaying N single-pod handlers (each its own lock
    acquisition) for pods that mostly resolve to the same handful of nodes
    anyway. Idempotent either way (see those methods' own already-tracked/
    already-gone filtering), so safe to run even when nothing has drifted.
    Pods not yet scheduled (spec.nodeName unset) are skipped - the
    spec.nodeName field handler picks those up once they are, same as always.
    Pods with a deletion_timestamp set are also skipped from "actual" (they
    are mid-termination, still returned by the API while blocked on kopf's
    own finalizer, but not really there) - otherwise a reconciliation tick
    landing between kopf's on.delete handler finishing (removing the pod from
    ClusterState) and the finalizer actually clearing would see the pod as
    newly-untracked and resurrect it: re-adding it to ClusterState and
    recreating its SG rules, fighting kopf's own finalizer removal and
    flapping the pod between removed/recreated indefinitely. Treating a
    terminating pod as absent instead just means it also lands in
    removed_keys if it's still tracked - a harmless no-op once kopf's own
    handler (or a prior reconciliation tick) has already removed it.

    known is snapshotted BEFORE the API list call, not after - deliberately.
    A pod's own event handler runs concurrently with this function, in a
    different thread, and can add it to ClusterState at any point. If known
    were read second (after the list call), a pod added in the gap between
    the two reads would land in known but not in the already-captured
    actual - misclassified as genuinely removed, tearing down a rule that
    was just legitimately created. Reading known first means such a pod
    instead lands in actual but not (the now-stale) known - misclassified
    as newly-untracked instead, which is a harmless no-op: handle_new_pods_
    batch already filters out anything ClusterState has by the time it runs.
    Reproduced live: a same-project elastic test's newly-scaled-out client
    pod had its rule created, then torn down again within the same second
    by a reconciliation tick that raced its creation this way.
    """
    known = {(pod.namespace, pod.name): pod for pod in ClusterState.get_pods()}

    try:
        pod_list = client.CoreV1Api().list_pod_for_all_namespaces().items
    except Exception as e:
        print(f"Reconcile: failed to list pods: {e}")
        return 0, 0

    actual = {}
    for p in pod_list:
        if p.metadata.deletion_timestamp is not None:
            continue
        node_name = p.spec.node_name
        if not node_name:
            continue
        pod_dict = {
            "metadata": {"name": p.metadata.name, "namespace": p.metadata.namespace, "labels": p.metadata.labels or {}},
            "spec": {"nodeName": node_name},
        }
        actual[(p.metadata.namespace, p.metadata.name)] = Watcher.create_pod_from_pod_dict(pod_dict)

    new_keys = set(actual) - set(known)
    removed_keys = set(known) - set(actual)

    if new_keys:
        print(f"Reconcile: found {len(new_keys)} untracked pod(s) - handling as a batch.")
        watchdog.handle_new_pods_batch({actual[key] for key in new_keys})
    if removed_keys:
        print(f"Reconcile: {len(removed_keys)} tracked pod(s) no longer exist - handling as a batch.")
        watchdog.handle_removed_pods_batch({known[key] for key in removed_keys})

    return len(new_keys), len(removed_keys)


def reconcile_once():
    new_count, removed_count = reconcile_pods_once()
    if new_count or removed_count:
        print(f"Reconcile: batch pass processed {new_count} untracked and {removed_count} stale pod(s).")


def reconciliation_loop(interval_seconds: int):
    while True:
        time.sleep(interval_seconds)
        try:
            reconcile_once()
        except Exception as e:
            print(f"Reconcile: unexpected error during batch reconciliation: {e}")


@kopf.on.resume('v1', 'pods')
def handle_existing_pod(body, name, namespace, **kwargs):
    node = body.get("spec", {}).get("nodeName")
    if node:
        pod_name = body.get('metadata', {}).get('name')
        print(f"Handling existing pod {pod_name}, scheduled on node {node}.")

        # Reconstruct pod object and pass to handler
        pod_object = Watcher.create_pod_from_pod_dict(body)
        print(f"Handling already existing pod object: {pod_object}")
        watchdog.handle_new_pod(pod_object)


# Handler for when a pod gets scheduled on a node. (handler specifically looks for changes in the spec.nodeName field)
@kopf.on.field('v1', 'pods', field='spec.nodeName')
def handle_new_pod(old, new, body, name, namespace, **kwargs):
    old_node = old
    new_node = new
    pod_name = body.get('metadata').get('name')
    node = body.get("spec").get("nodeName")
   
   # Printing handler being called.
    print(f"New pod {pod_name}! old_node = {old_node}, new_node = {new_node}.")

    # Actually handling the new pod event (that is actually scheduled on a node)
    pod_object = Watcher.create_pod_from_pod_dict(body)
    print(f"Handling the new pod object: {pod_object}")
    watchdog.handle_new_pod(pod_object)

@kopf.on.delete('v1', 'pods')
def handle_removed_pod(body, **kwargs):
    pod_object = Watcher.create_pod_from_pod_dict(body)
    pod_name = pod_object.name
    print(f"Removing pod {pod_name}")
    watchdog.handle_removed_pod(pod_object)

@kopf.on.resume('v1', 'namespaces')
@kopf.on.create('v1', 'namespaces')
@kopf.on.update('v1', 'namespaces')
def handle_new_or_updated_namespace(body, **kwargs):
    name, labels = Watcher.create_namespace_from_dict(body)
    print(f"Registering namespace {name} with labels {labels}")
    watchdog.handle_new_namespace(name, labels)

@kopf.on.delete('v1', 'namespaces')
def handle_removed_namespace(body, **kwargs):
    name, _ = Watcher.create_namespace_from_dict(body)
    print(f"Removing namespace {name}")
    watchdog.handle_removed_namespace(name)

@kopf.on.resume('networking.k8s.io', 'v1', 'networkpolicies')
@kopf.on.create('networking.k8s.io', 'v1', 'networkpolicies')
def handle_new_policy(body, **kwargs):
    policy = Watcher.create_policy_from_policy_dict(body)
    watchdog.handle_new_policy(policy)

@kopf.on.delete('networking.k8s.io', 'v1', 'networkpolicies', retries=5)
def handle_removed_policy(body, **kwargs):
    global last_run_time

    with remove_handler_lock:
        now = time.time()
        time_since_last = now - last_run_time

        if time_since_last < WAIT_TIME:
            delay = WAIT_TIME - time_since_last
            print(f"⏳ Waiting {delay:.1f}s before running handler for handle_removed_policy")
            time.sleep(delay)  # block this thread, allow others

        last_run_time = time.time()
        print(f"✅ Running handler for {handle_removed_policy} at {time.strftime('%X')}")

        try: 
            policy = Watcher.create_policy_from_policy_dict(body)
            watchdog.handle_removed_policy(policy)
        except Exception as e:
            raise kopf.TemporaryError(f"There was a problem removing the policy {policy.name} \n {e}", delay=2)

@kopf.on.cleanup()
def show_cluster_state(**kwargs):
    print(ClusterState())

if __name__ == "__main__":
    kopf.run(
        standalone=True,          # Optional: disables multiprocessing
        clusterwide=True,         # Watch all namespaces, not just one.
    )



