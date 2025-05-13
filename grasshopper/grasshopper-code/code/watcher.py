from kubernetes import watch, client, config
from watchdog import WatchDog
from classes import *
import time
import os
import pandas as pd
import csv


RESULTS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../experiments/latency/results/handle-times/")
OUTPUT_FOLDER = None
BURST = 100
ITERATION = 1



class Watcher:
    """
    A class to watch Kubernetes events for Pods, Network Policies.
    """

    def __init__(self, PNS_scenario, namespace):
        self.namespace = namespace
        self.watchdog = WatchDog(PNS_scenario)
        self.core_api = client.CoreV1Api()
        self.networking_api = client.NetworkingV1Api()
        self.networking_v1 = client.NetworkingV1Api()
        self.k8s_watcher: watch.Watch = watch.Watch()
        self.initialize_output_file()

    def initialize_output_file(self):
        global OUTPUT_FOLDER
        output_folder_path = os.path.join(RESULTS_FOLDER, f"burst-{BURST}")
        output_file_path = os.path.join(output_folder_path, f"{ITERATION}-pod-handle-time-iteration.csv")

        if not os.path.isdir(output_folder_path):
            os.mkdir(output_folder_path)

        if not os.path.isfile(output_file_path):
            timings_df = pd.DataFrame(columns=['pod_name', 'handle_time'])
            timings_df.to_csv(output_file_path)

        OUTPUT_FOLDER = output_file_path

    def write_pod_handle_time(self, pod_name, handle_time):
        with open(OUTPUT_FOLDER, mode='a', newline='') as timings_csv:
            writer = csv.writer(timings_csv)
            writer.writerow([pod_name, handle_time])

    def watch_pods(self):
        print(f"Watching pods now in namespace {self.namespace} ...")
        for event in self.k8s_watcher.stream(
            self.core_api.list_namespaced_pod, namespace=self.namespace
        ):
            self.handle_pod_event(event)

    def watch_policies(self):
        print(f"Watching policies now in namespace {self.namespace} ...")
        for event in self.k8s_watcher.stream(
            self.networking_api.list_namespaced_network_policy, namespace=self.namespace
        ):
            self.handle_policy_event(event)

    def watch_services(self):
        print("Watching services now...")
        for event in self.k8s_watcher.stream(
            self.core_api.list_service_for_all_namespaces
        ):
            event_object = event["object"]
            name = event_object.metadata.name
            print(f"Service: {name}")


    def handle_pod_event(self, event):
        # Get the event type.
        event_type = event["type"]
        pod = event["object"]

        # Here, the pod will be assigned to a node. (So we're handling this as a new-pod-event)
        if event_type == "MODIFIED" and pod.spec.node_name:
            pod = Watcher.create_pod_from_pod_event(event)
            self.watchdog.handle_new_pod(pod)
            print(pod)

            # Also log the handle event time.
            # pod_name = pod.name
            # handle_time = time.time()
            # self.write_pod_handle_time(pod_name, handle_time)

        elif event_type == "DELETED":
            # Create the corresponding Pod-object from k8s-event.
            pod = Watcher.create_pod_from_pod_event(event)
            print(pod)

            # Handle the removed Pod.
            self.watchdog.handle_removed_pod(pod)

    def handle_policy_event(self, event):
        print(f"Handling policy event")
        event_type = event["type"]
        policy = Watcher.create_policy_from_policy_event(event)

        if event_type == "ADDED":
            self.watchdog.handle_new_policy(policy)
        elif event_type == "DELETED":
            self.watchdog.handle_removed_policy(policy)
        elif event_type == "MODIFIED":
            pass

    def handle_service_event(self, event):
        event_type = event["type"]
        if event_type == "ADDED":
            pass
        elif event_type == "DELETED":
            pass
        elif event_type == "MODIFIED":
            pass

    @staticmethod
    def create_pod_from_pod_event(event) -> Pod:
        """
        This method creates a Pod-object from a pod-event.

        Args:
         - event: Assumed to be a pod event.

        Returns:
         - pod : Pod | A pod object from the grasshopper model.

        """
        # Parse the event.
        event_object = event["object"]
        metadata = event_object.metadata
        spec = event_object.spec

        # Get relevant information.
        name = metadata.name
        labels = metadata.labels
        node_name = spec.node_name

        # Create pod-attributes.
        label_set = LabelSet(labels)

        if node_name:
            node = Node(node_name)
        else:
            node = None

        return Pod(name, LabelSet(labels), node)

    @staticmethod
    def create_pod_from_pod_object(pod_object) -> Pod:
        """
        This method creates a Pod-object from a pod-event.

        Args:
         - event: Assumed to be a pod event.

        Returns:
         - pod : Pod | A pod object from the grasshopper model.

        """
        # Parse the event.
        event_object = pod_object
        metadata = event_object.metadata
        spec = event_object.spec

        # Get relevant information.
        name = metadata.name
        labels = metadata.labels
        node_name = spec.node_name

        # Create pod-attributes.
        label_set = LabelSet(labels)

        if node_name:
            node = Node(node_name)
        else:
            node = None

        return Pod(name, LabelSet(labels), node)

    @staticmethod
    def create_policy_from_policy_event(event) -> Policy:
        # Get relevant information from event.
        event_object = event["object"]
        metadata = event_object.metadata
        spec = event_object.spec

        # Get relevant information.
        name = metadata.name
        egress = spec.egress
        ingress = spec.ingress
        pod_selector = spec.pod_selector

        # Construct the selected-attribute.
        selected = None
        if pod_selector.match_labels:
            selected = Watcher.create_selected(pod_selector.match_labels)
        else:
            selected = LabelSet(dict())

        # Construct allow-list.
        allow_list = []
        if ingress:
            allow_list_ingress = Watcher.create_allow_list_ingress(ingress)
            allow_list = allow_list + allow_list_ingress

        if egress:
            allow_list_egress = Watcher.create_allow_list_egress(egress)
            allow_list = allow_list + allow_list_egress

        return Policy(name, selected, allow_list)
    
    @staticmethod
    def create_policy_from_policy_object(policy_object) -> Policy:
        # Get relevant information from event.
        event_object = policy_object
        metadata = event_object.metadata
        spec = event_object.spec

        # Get relevant information.
        name = metadata.name
        egress = spec.egress
        ingress = spec.ingress
        pod_selector = spec.pod_selector

        # Construct the selected-attribute.
        selected = None
        if pod_selector.match_labels:
            selected = Watcher.create_selected(pod_selector.match_labels)
        else:
            selected = LabelSet(dict())

        # Construct allow-list.
        allow_list = []
        if ingress:
            allow_list_ingress = Watcher.create_allow_list_ingress(ingress)
            allow_list = allow_list + allow_list_ingress

        if egress:
            allow_list_egress = Watcher.create_allow_list_egress(egress)
            allow_list = allow_list + allow_list_egress

        return Policy(name, selected, allow_list)

    @staticmethod
    def create_allow_list_ingress(
        ingress_list,
    ) -> list[tuple[LabelSet | CIDR, Traffic]]:
        allow_list = []
        for ingress in ingress_list:
            if ingress._from:
                for entry in ingress._from:
                    # parse the field to create labelset.
                    labelset = Watcher.parse_networkpolicypeer_field(entry)

                    # if there is a ports-field.
                    if ingress.ports:
                        # Create allow-tuples.
                        for port in ingress.ports:
                            traffic = Traffic(INGRESS, port.port, port.protocol)
                            tuple = (labelset, traffic)

                            allow_list.append(tuple)

        return allow_list

    @staticmethod
    def create_allow_list_egress(egress_list):
        allow_list = []
        for egress in egress_list:
            if egress.to:
                for entry in egress.to:
                    labelset = Watcher.parse_networkpolicypeer_field(entry)

                    # if there is a ports-field.
                    if egress.ports:
                        for port in egress.ports:
                            traffic = Traffic(EGRESS, port.port, port.protocol)
                            tuple = (labelset, traffic)

                            allow_list.append(tuple)

        return allow_list

    @staticmethod
    def parse_networkpolicypeer_field(entry) -> LabelSet:
        labels = dict()
        if entry.ip_block:
            return CIDR(str(entry.ip_block.cidr))
        else:
            if entry.namespace_selector and entry.namespace_selector.match_labels:
                labels.update(entry.namespace_selector.match_labels)
            if entry.pod_selector and entry.pod_selector.match_labels:
                labels.update(entry.pod_selector.match_labels)

            return LabelSet(labels)

    @staticmethod
    def create_selected(label_set: dict[str, str]):
        """
        This method creates the selected-attribute from a given podSelector-field.
        """
        return LabelSet(label_set)
