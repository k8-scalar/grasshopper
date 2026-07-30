from kubernetes import client, config
from labels import *
import random 
import time
import argparse
import sys


NAMESPACE = 'test-thesis'


class ClusterSimulator:
    """
    A class to simulate a cluster environment for testing purposes.

    Attributes:
        - namespace (str): The namespace in which to create the test pod.
    """


    def __init__(self, namespace):
        self.namespace = namespace
        self.initialize_cluster_config()
        self.api = client.CoreV1Api()

    def initialize_cluster_config(self):
        """ Initializes the cluster configuration. """
        config.load_kube_config()

    def create_test_pod(self, index: int, labelset: dict): 
        """ Creates a test-pod in the cluster with a random labelset."""

        pod_name = f"test-pod-{index}"

        pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"namespace" : self.namespace, "name": pod_name, "labels": labelset},
            "spec": {
                "containers": [{
                    "name": "busy-container",
                    "image": "busybox",
                    "command": ["sleep", "30"]  # Simulating work
                }]
            }
        }

        try:
            self.api.create_namespaced_pod(namespace=self.namespace, body=pod_manifest)
            print(f"[+] Created pod: {pod_name}")
        except Exception as e:
            print(f"[!] Failed to create pod {pod_name}: {e}")


    def create_pod_burst(self, nb_pods):
        """ 
        Function to create a burst of pods. It cycles through all possible combinations of labelsets,
        resulting in pods where the labelsets are uniformly distributed.

        Args:
            nb_pods (int): The number of pods to create.
        
        """
        created_pods_index = 0

        print(f"Creating a burst of {nb_pods} pods.")
        
        # Cycle through all possible combinations of labels.
        while created_pods_index < (nb_pods - 1):
            for app_label_value in app_label_values:
                for role_label_value in role_label_values:

                    # Break when amount of created pods has reached it's limit.
                    if created_pods_index >= nb_pods:
                        break
                        
                    # Create the labelset (which is a dictionary for the python framework)
                    label_dict = {'app': app_label_value, 'role': role_label_value}

                    # Create the test-pod with the generated labelset.
                    self.create_test_pod(created_pods_index, label_dict)

                    # Increment pod index.
                    created_pods_index += 1

        print(f"Pod burst done. Created {created_pods_index} pods.")


    def remove_test_pod(self, pod_name): 
        """ Removes a pod by name."""
        try:
            self.api.delete_namespaced_pod(name=pod_name, namespace=self.namespace)
            print(f"[-] Deleted pod: {pod_name}")
        except Exception as e:
            print(f"[!] Failed to delete pod {pod_name}: {e}")

def parse_args():
    parser = argparse.ArgumentParser(description="Simulate a burst of pod creation in a Kubernetes cluster.")
    parser.add_argument("--namespace", type=str, required=True, help="Namespace you want to create the pods in.")
    parser.add_argument("--num-pods", type=int, required=True, help="Number of pods to create in the burst.")
    return parser.parse_args()


if __name__ == "__main__":
    # Reading arguments.
    args = parse_args()
    namespace = args.namespace
    num_pods = args.num_pods

    # Creating clusterSimulator and creating burst.
    clusterSimulator = ClusterSimulator(namespace)
    clusterSimulator.create_pod_burst(num_pods)

    # Exiting the script after finishing the burst.
    sys.exit(0)

