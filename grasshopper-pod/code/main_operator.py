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
        # Process every already-existing NetworkPolicy before detaching
        # "default" from workers - detaching any earlier leaves a real
        # ingress gap for whatever traffic those policies were supposed to
        # open (confirmed live - see README_v2.md). This means any
        # bootstrap-critical NetworkPolicy (e.g. Typha's) must be applied
        # BEFORE this pod is deployed, not after.
        process_existing_network_policies()
        detach_defaultSG()

@kopf.on.startup()
def startup_handler(settings: kopf.OperatorSettings, **kwargs):
    settings.execution.max_workers = MAX_WORKERS
    settings.posting.backoff = DELAY
    logger.info(f"Starting Operator with {MAX_WORKERS} workers.")
    startup()

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



