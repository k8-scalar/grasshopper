import platform
import subprocess
import xmlrpc.client
import json
import time
import os
import re
from classes import LabelSet, Node, Pod

CHECK_PODS_INTERVAL_MS = 100  # Check pods every CHECK_PODS_INTERVAL milliseconds

master_ip = os.getenv("MASTER_IP", "192.168.59.100")  # Default value if not set
master_port = os.getenv("MASTER_PORT", "9000")  # Default value if not set


class KubeletWatch:
    def __init__(self):
        try:
            print(f"Trying to connect to master at {master_ip}:{master_port}")
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
        print(f"New pod: {pod.name}")
        self.master.handle_new_pod(pod)

    def handle_modified_pod(self, pod: Pod):
        print(f"Modified pod: {pod.name}")
        self.master.handle_modified_pod(pod)

    def handle_removed_pod(self, pod: Pod):
        print(f"Removed pod: {pod.name}")
        self.master.handle_removed_pod(pod)

    def start(self):
        print("KubeletWatch started.")
        node_ip = os.getenv("NODE_IP")

        while True:
            cmd = ["kubeletctl", "pods", "--raw", "--server", node_ip]
            try:
                result = subprocess.run(
                    cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                response = result.stdout

                # Use regular expression to find the JSON content
                json_match = re.search(r"(\{.*\})", response, re.DOTALL)
                if json_match:
                    json_content = json_match.group(1)
                    pod_list = json.loads(json_content)
                else:
                    print("No JSON content found in the response.")
                    continue

            except subprocess.CalledProcessError as e:
                print(f"Command '{cmd}' returned non-zero exit status {e.returncode}.")
                print(f"Error output: {e.stderr}")
                continue
            except json.JSONDecodeError as e:
                print(f"Failed to decode JSON response: {response}")
                continue

            new_pods = set(
                Pod(
                    name=item["metadata"]["name"],
                    label_set=LabelSet(labels=item["metadata"]["labels"]),
                    node=Node(name=item["spec"]["nodeName"]),
                )
                for item in pod_list["items"]
            )

            # Check for added pods
            added_pods = new_pods - self.pods
            if added_pods:
                print("---------------------------------")
                print(f"{len(added_pods)} new pod(s) found.")
                for pod in added_pods:
                    self.handle_new_pod(pod)
                print("---------------------------------")

            # Check for removed pods
            removed_pods = self.pods - new_pods
            if removed_pods:
                print("---------------------------------")
                print(f"{len(removed_pods)} pod(s) removed.")
                for pod in removed_pods:
                    self.handle_removed_pod(pod)
                print("---------------------------------")

            self.pods = new_pods

            time.sleep(CHECK_PODS_INTERVAL_MS / 1000)


if __name__ == "__main__":
    w = KubeletWatch()
    w.start()
