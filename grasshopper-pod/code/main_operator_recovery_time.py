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

# File paths.
RESULTS_PATH = "/mnt/nfs_share/recovery_times/startup_time.txt"

# Specify the namespace you want to manage.
NAMESPACE = 'test-thesis'

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

# Startup timing variables
startup_start_time = None
last_resume_handler_time = None
startup_timer_lock = threading.Lock()
startup_timer_thread = None
STARTUP_TIMEOUT = 10 # seconds after last resume handler to consider startup complete

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

logger = logging.getLogger(__file__)

def write_startup_time_to_file(startup_time_seconds):
    """Write the startup time to the results file."""
    with open(RESULTS_PATH, 'w') as f:
        f.write(f"{startup_time_seconds}")
    logger.info(f"Startup time written to file: {startup_time_seconds:.3f} seconds")
    print(f"⏱️ Operator startup completed in {startup_time_seconds:.3f} seconds.")
    print("🏁 Recovery time measurement complete. Requesting operator shutdown...")
    
    # Request kopf to stop the operator gracefully
    kopf.stop_flag.set()


def startup_completion_timer():
    """Timer function that waits for STARTUP_TIMEOUT seconds after the last resume handler."""
    global startup_timer_thread
    
    # Wait a short time for initial resume handlers to potentially execute
    initial_wait_time = 2
    time.sleep(initial_wait_time)
    
    while True:
        time.sleep(1)  # Check every second
        
        with startup_timer_lock:
            current_time = time.time()
            
            # If no resume handlers executed after initial wait, consider startup complete
            if last_resume_handler_time is None:
                continue
                
            time_since_last_resume = current_time - last_resume_handler_time
            
            if time_since_last_resume >= STARTUP_TIMEOUT:
                # Startup is complete
                startup_time = last_resume_handler_time - startup_start_time
                write_startup_time_to_file(startup_time)
                startup_timer_thread = None
                break

def update_resume_handler_timestamp():
    """Update the timestamp of the last resume handler execution."""
    global last_resume_handler_time
    
    with startup_timer_lock:
        last_resume_handler_time = time.time()
        logger.info(f"⏰ Resume handler executed at {time.strftime('%H:%M:%S')}")
        print(f"⏰ Resume handler executed, updating startup timer")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['PNS', 'PLS'], required=True)
    return parser.parse_args()

def initialize_cluster_configuration():
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
        config.load_incluster_config()
    else:
        config.load_kube_config()

def startup():
    global MODE, watcher, watchdog
    args = parse_args()
    MODE = args.mode

    print(f"🚀 Starting Kopf operator in mode: {MODE}, watching the {NAMESPACE} namespace.")

    # Initialising OpenStack Client.
    OpenStackClient()
    
    # Initializing cluster configuration.
    initialize_cluster_configuration()

    # Initializing Cluster State.
    ClusterState().initialize_light(PNS_scenario=(MODE == "PNS"), namespace=NAMESPACE)

    # If mode is PNS, create a sg for every node.
    if MODE == "PNS":
        create_sg_per_node(delete_existing_rules=True)

    # Create Watcher.
    watcher = Watcher(PNS_scenario=(MODE == "PNS"))
    watchdog = WatchDog(PNS_scenario=(MODE == "PNS"))

@kopf.on.startup()
def startup_handler(settings: kopf.OperatorSettings, **kwargs):
    global startup_start_time, startup_timer_thread
    
    # Record startup time
    startup_start_time = time.time()
    logger.info(f"🚀 Operator startup timer started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    settings.execution.max_workers = MAX_WORKERS
    settings.posting.backoff = DELAY
    logger.info(f"Starting Operator with {MAX_WORKERS} workers.")
    startup()
    
    # Start the startup completion timer in a separate thread
    startup_timer_thread = threading.Thread(target=startup_completion_timer, daemon=True)
    startup_timer_thread.start()

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
    
    # Update resume handler timestamp for startup timing
    update_resume_handler_timestamp()
    
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

@kopf.on.resume('networking.k8s.io', 'v1', 'networkpolicies')
def handle_existing_policy(body, **kwargs):
    policy = Watcher.create_policy_from_policy_dict(body)
    watchdog.handle_new_policy(policy)

    # Update resume handler timestamp for startup timing
    update_resume_handler_timestamp()
    
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
        namespace=NAMESPACE
    )



