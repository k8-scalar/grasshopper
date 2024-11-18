import platform
import subprocess
import xmlrpc.client
import json
import time
import os

from classes import Pod

master_ip = os.getenv("MASTER_IP", "192.168.59.107")  # Default value if not set
master_port = os.getenv("MASTER_PORT", "9000")  # Default value if not set


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
        print("Created KubeletWatch instance.")

    # functions to handle added / removed / modified pods.
    def handle_new_pod(self, pod: Pod):
        print(f"New pod: {pod}")
        self.master.handle_new_pod(pod)

    def handle_modified_pod(self, pod: Pod):
        print(f"Modified pod: {pod}")
        self.master.handle_modified_pod(pod)

    def handle_removed_pod(self, pod: Pod):
        print(f"Removed pod: {pod}")
        self.master.handle_removed_pod(pod)

    def start(self):
        print("KubeletWatch started.")
        node_ip = os.getenv("NODE_IP")

        while True:
            cmd = ["kubeletctl", "runningpods", "--server", node_ip]
            try:
                response = subprocess.check_output(cmd, text=True)
                pod_list = json.loads(response)
            except subprocess.CalledProcessError as e:
                print(f"Command '{cmd}' returned non-zero exit status {e.returncode}.")
                print(f"Error output: {e.output}")
                continue
            except json.JSONDecodeError as e:
                print(f"Failed to decode JSON response: {response}")
                continue

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
