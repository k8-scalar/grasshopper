import kopf
import argparse
import os
from cluster_state import ClusterState
from openstackfiles.create_sg_per_node import create_sg_per_node
from kubernetes import config
from operator_code.watcher_operator import Watcher
import logging

# Specify the namespace you want to manage.
NAMESPACE = 'default'

MODE = None
watcher = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['PNS', 'PLS'], required=True)
    return parser.parse_args()

def initialize_cluster_configuration():
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
        config.load_incluster_config()
    else:
        config.load_kube_config()

@kopf.on.startup()
def startup_handler(**kwargs):
    global MODE, watcher
    args = parse_args()
    MODE = args.mode

    print(f"🚀 Starting Kopf operator in mode: {MODE}, watching the {NAMESPACE} namespace.")
    
    # Initializing cluster configuration.
    initialize_cluster_configuration()

    # Initializing Cluster State.
    ClusterState().initialize(PNS_scenario=(MODE == "PNS"), namespace=NAMESPACE)

    # If mode is PNS, create a sg for every node.
    if MODE == "PNS":
        create_sg_per_node(delete_existing_rules=True)

    # Create Watcher.
    watcher = Watcher(PNS_scenario=(MODE == "PNS"))

@kopf.on.event('v1', 'pods')
def handle_pod_event(event, body, **kwargs):
    event_type = event['type']
    watcher.handle_pod_event(event_type, body)  


@kopf.on.event('networking.k8s.io', 'v1', 'networkpolicies')
def handle_policy_event(event, body, **kwargs):
    event_type = event['type']
    watcher.handle_policy_event(event_type, body)

if __name__ == "__main__":
    kopf.run(
        standalone=True,          # Optional: disables multiprocessing
        namespace=NAMESPACE
    )



