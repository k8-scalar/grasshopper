import kopf
import argparse
import os
from cluster_state import ClusterState
from openstackfiles.create_sg_per_node import create_sg_per_node
from openstackfiles.openstack_client import OpenStackClient
from kubernetes import config
from operator_code.watcher_operator import Watcher
from watchdog import WatchDog
import logging
import time
import pandas as pd
import csv
import threading


# Specify the namespace you want to manage.
NAMESPACE = 'test-thesis'

MODE = None
watcher = None
watchdog = None

# File paths.
NFS_PATH = "/mnt/nfs_share/"
LATENCY_RESULTS_FOLDER_PATH = NFS_PATH + "latency_results/"
LATENCY_RESULTS_FILE_PATH = os.path.join(LATENCY_RESULTS_FOLDER_PATH, "latency_results.csv")

# kopf settings.
MAX_WORKERS = 20
DELAY = 2

# Throttling handlers (remove_policy)
WAIT_TIME = 1
last_run_time = 0
remove_handler_lock = threading.Lock()

# File writing synchronization
file_write_lock = threading.Lock()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

logger = logging.getLogger(__file__)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['PNS', 'PLS'], required=True)
    return parser.parse_args()

def initialize_cluster_configuration():
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
        config.load_incluster_config()
    else:
        config.load_kube_config()

def initialize_output_file():
    latency_df = pd.DataFrame(columns=['pod_name', 'event_time', 'handle_time'])
    latency_df.to_csv(LATENCY_RESULTS_FILE_PATH)

def write_pod_handle_time(pod_name, event_time, handle_time):
    with file_write_lock:  # Ensure thread-safe file writing
        with open(LATENCY_RESULTS_FILE_PATH, mode='a', newline='') as latency_results:
            writer = csv.writer(latency_results)
            writer.writerow([pod_name, event_time, handle_time])

def startup():
    global MODE, watcher, watchdog
    args = parse_args()
    MODE = args.mode

    print(f"🚀 Starting Kopf operator in mode: {MODE}, watching the {NAMESPACE} namespace.")

    print(f"Initialising latency-results.csv file")
    initialize_output_file()
    
    # Initializing cluster configuration.
    initialize_cluster_configuration()

    # Initializing Openstack Client.
    OpenStackClient()

    # Initializing Cluster State.
    ClusterState().initialize(PNS_scenario=(MODE == "PNS"), namespace=NAMESPACE)

    # If mode is PNS, create a sg for every node.
    if MODE == "PNS":
        create_sg_per_node(delete_existing_rules=True)

    # Create Watcher.
    watcher = Watcher(PNS_scenario=(MODE == "PNS"))
    watchdog = WatchDog(PNS_scenario=(MODE == "PNS"))

@kopf.on.startup()
def startup_handler(settings: kopf.OperatorSettings, **kwargs):
    settings.execution.max_workers = MAX_WORKERS
    settings.posting.backoff = DELAY
    logger.info(f"Starting Operator with {MAX_WORKERS} workers.")
    startup()

# Handler for when a pod gets scheduled on a node. (handler specifically looks for changes in the spec.nodeName field)
@kopf.on.field('v1', 'pods', field='spec.nodeName')
def handle_new_pod(old, new, body, name, namespace, **kwargs):
    # TIMING: registering event start time.
    tic = time.time()
    print(f"Registering time when event comes in for {body.get('metadata').get('name')}: {tic}")

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

    # TIMING: registering handled time.
    toc = time.time()
    print(f"Registering time when event is handled for {pod_name}: {toc}")

    # Writing timings to event-latency file in in nfs-share.
    write_pod_handle_time(pod_name, tic, toc)


@kopf.on.delete('v1', 'pods')
def handle_removed_pod(body, **kwargs):
    pod_object = Watcher.create_pod_from_pod_dict(body)
    pod_name = pod_object.name
    print(f"Removing pod {pod_name}")
    watchdog.handle_removed_pod(pod_object)

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

        print(f"✅ Running handler for {handle_removed_policy} at {time.strftime('%X')}")

        try: 
            policy = Watcher.create_policy_from_policy_dict(body)
            watchdog.handle_removed_policy(policy)
            # Update last_run_time AFTER the handler completes successfully
            last_run_time = time.time()
        except Exception as e:
            # Update last_run_time even on failure to prevent rapid retries
            last_run_time = time.time()
            raise kopf.TemporaryError(f"There was a problem removing the policy {policy.name} \n {e}", delay=2)

@kopf.on.cleanup()
def cleanup(**kwargs):
    logger.info("Cleanup handler being called!")
    logger.info("================== STATE OF CLUSTER STATE WHEN GRASSHOPPER IS BEING TERMINATED =============")
    logger.info(ClusterState().load_cluster_state_from_database())
    logger.info("Now cleaning up database.")
    ClusterState.clean_database() # Comment this out to simulate a "failure", and it load the cluster state from database.

if __name__ == "__main__":
    kopf.run(
        standalone=True,          # Optional: disables multiprocessing
        namespace=NAMESPACE
    )



