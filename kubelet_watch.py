import platform
import subprocess
import xmlrpc.client
import json
import time

from classes import Pod
from kubelet_watch_server import master_ip, master_port


class KubeletWatch:
    def __init__(self):
        try:
            self.master = xmlrpc.client.ServerProxy(f"http://{master_ip}:{master_port}")
            node_name = platform.node()
            is_connected = self.master.on_connect_worker(node_name)
            if is_connected:  # register the worker to the master
                print("Connected to master.")
            else:
                print("Failed to connect to master.")
                exit(1)
        except Exception as e:
            print(f"Failed to connect to master: {e}")
            exit(1)
        self.pods = set()

    # functions to handle added / removed / modified pods.
    def handle_new_pod(self, pod: Pod):
        self.master.handle_new_pod(pod)

    def handle_modified_pod(self, pod: Pod):
        self.master.handle_modified_pod(pod)

    def handle_removed_pod(self, pod: Pod):
        self.master.handle_removed_pod(pod)

    def start(self):
        while True:
            cmd = ["kubeletctl", "runningpods"]
            response = subprocess.check_output(
                cmd, text=True, stderr=subprocess.DEVNULL
            )

            pod_list = json.loads(response)
            new_pods = set(item["metadata"]["name"] for item in pod_list["items"])

            # Check for added pods
            added_pods = new_pods - self.pods
            if added_pods:
                print("---------------------------------")
                print(f"{len(added_pods)} new pod(s) found.")
                for pod in added_pods:
                    print(pod)
                    self.handle_new_pod(pod)
                print("---------------------------------")

            # Check for removed pods
            removed_pods = self.pods - new_pods
            if removed_pods:
                print("---------------------------------")
                print(f"{len(removed_pods)} pod(s) removed.")
                for pod in removed_pods:
                    print(pod)
                    self.handle_removed_pod(pod)
                print("---------------------------------")

            self.pods = new_pods

            time.sleep(0.01)


if __name__ == "__main__":
    w = KubeletWatch()
    w.start()
