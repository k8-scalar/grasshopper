from kubernetes import client, config
from labels import *
import random 
import time


# Modes of the cluster simulation.
CLUSTER_MODES = ["normal", "heavy", "light", "normal with spikes"]

# Maximum number of pods.
CLUSTER_SIZE = 500

# Chance of a spike
SPIKE_CHANCE = 0.05

# pods per milliesecond
SPIKE_RATE = 0.1


class ClusterSimulator:
    """
    A class to simulate a cluster environment for testing purposes.

    Attributes:
        - namespace (str): The namespace in which to create the test pod.
        - cluster_size (int): The maxium number of pods in the cluster. (What the cluster can handle)

    """
    def __init__(self, namespace, cluster_size):
        self.initialize_cluster_config()
        self.api = client.CoreV1Api()
        self.namespace = namespace
        self.pod_count = 0


    def initialize_cluster_config(self):
        """ Initializes the cluster configuration. """
        config.load_kube_config()
    
    def create_random_labels(self):
        """ A function to create random labels for a test pod. """

        labels = {}

        sub_labels_list = random.sample(all_labels, k=random.randint(1, len(all_labels)))
        
        for sub_labels in sub_labels_list:
            for key, values_list in sub_labels.items():
                labels.update({key: random.choice(values_list)})

        return labels


    def create_test_pod(self): 
        """ Creates a test-pod in the cluster with a random labelset."""

        pod_name = f"test-pod-{self.pod_count}"
        labels = self.create_random_labels()

        pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": pod_name, "labels": labels,},
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
            self.pod_count += 1
            print(f"[+] Created pod: {pod_name}")
        except Exception as e:
            print(f"[!] Failed to create pod {pod_name}: {e}")


    def remove_test_pod(self, pod_name): 
        """ Removes a pod by name."""
        try:
            self.api.delete_namespaced_pod(name=pod_name, namespace=self.namespace)
            print(f"[-] Deleted pod: {pod_name}")
        except Exception as e:
            print(f"[!] Failed to delete pod {pod_name}: {e}")

    def create_network_policy(self): 
        pass 
    
    def remove_network_policy(self):
        pass 

    def simulate_cluster(self):
        """ Simulates the cluster activity by creating / removing pods and 
            applying changes in network policies.
         """
        
        try:
            while True: 
                self.create_test_pod()
                time.sleep(5)

        except KeyboardInterrupt:
            print("Stopped simulation, cleaning up cluster.")
            self.clean_cluster()

    def normal_workload(self):
        pass

    def heavy_workload(self):
        pass
    
    def simulate_policy_changes(self):
        pass 

    def clean_cluster(self):
        print("Cleaning Cluster ...")
        for i in range(0, self.pod_count):
            self.remove_test_pod(f"test-pod-{i}")

if __name__ == "__main__":
    # Create a cluster simulator instance
    clusterSimulator = ClusterSimulator('default', CLUSTER_SIZE)
    clusterSimulator.simulate_cluster()