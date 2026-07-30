from watcher import Watcher
import argparse
from openstackfiles.create_sg_per_node import create_sg_per_node
from cluster_state import ClusterState
import threading
from kubernetes import config, client, watch
import os

NAMESPACE = 'test-thesis'

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['PNS', 'PLS'], required=True)
    return parser.parse_args()

def watch_pods():
    Watcher(PNS_scenario=True, namespace=NAMESPACE).watch_pods()

def watch_policies():
    Watcher(PNS_scenario=True, namespace=NAMESPACE).watch_policies()

def watch_policies_PLS():
    Watcher(PNS_scenario=False, namespace=NAMESPACE).watch_policies()

def watch_pods_PLS():
    Watcher(PNS_scenario=False, namespace=NAMESPACE).watch_pods()

def start_watch_PNS():
    print("Running in PNS-mode...")
    create_sg_per_node(delete_existing_rules=True)
    ClusterState().initialize(PNS_scenario=True, namespace=NAMESPACE)

    policies_thread = threading.Thread(target=watch_policies)
    pods_thread = threading.Thread(target=watch_pods)

    policies_thread.start()
    pods_thread.start()

def start_watch_PLS():
    print("Running in PLS-mode...")
    ClusterState().initialize(PNS_scenario=False, namespace=NAMESPACE)
    policies_thread = threading.Thread(target=watch_policies_PLS)
    pods_thread = threading.Thread(target=watch_pods_PLS)

    policies_thread.start()
    pods_thread.start()

def initialize_cluster_configuration():
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
        print("Running inside a Kubernetes Pod. Using in-cluster configuration.")
        config.load_incluster_config()  # Load in-cluster config
    else:
        print("Running locally. Using kubeconfig.")
        config.load_kube_config()  # Load kubeconfig for local development

def main():
    args = parse_args()

    initialize_cluster_configuration()
    
    if args.mode == 'PNS':
        print("🐝 Starting GrassHopper in PNS mode")
        start_watch_PNS()
    elif args.mode == 'PLS':
        print("🌿 Starting GrassHopper in PLS mode")
        start_watch_PLS()

if __name__ == "__main__":
    main()