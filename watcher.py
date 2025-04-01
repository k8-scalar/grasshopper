import os
from kubernetes import watch, client, config
from watchdog import WatchDog
from classes import *


class Watcher:
    """
    A class to watch Kubernetes events for Pods, Network Policies, and Services.

    Methods
    -------
    __init__():
        Initializes the Watcher class, loads Kubernetes configuration, and sets up APIs and watcher.

    load_config():
        Loads the Kubernetes configuration.

    watch_all_events():
        Watches all events across all namespaces and handles them based on their kind.

    watch_policies():
        Watches NetworkPolicy events across all namespaces.

    watch_services():
        Watches Service events across all namespaces.

    handle_pod_event(event):
        Handles Pod events based on their type (ADDED, DELETED).

    handle_policy_event(event):
        Handles NetworkPolicy events based on their type (ADDED, DELETED, MODIFIED).

    handle_service_event(event):
        Handles Service events based on their type (ADDED, DELETED, MODIFIED).
    """

    def __init__(self, PNS_scenario=True):
        self.load_config()
        self.watchdog = WatchDog(PNS_scenario)
        self.core_api = client.CoreV1Api()
        self.networking_api = client.NetworkingV1Api()
        self.networking_v1 = client.NetworkingV1Api()
        self.k8s_watcher: watch.Watch = watch.Watch()

    def load_config(self):
        """
        Loads the Kubernetes configuration.

        This method uses the `config.load_kube_config()` function to load the
        Kubernetes configuration from the default location, typically found
        in the user's home directory under `.kube/config`.

        Raises:
            ConfigException: If the configuration file cannot be loaded.
        """
        config.load_kube_config()

    def watch_all_events(self):
        """
        Watches and processes all Kubernetes events.

        This method continuously streams events from all namespaces in the Kubernetes cluster
        and processes them based on their type. It delegates handling of specific event types
        to corresponding handler methods.
        """
        pass

    def watch_pods(self):
        namespace = os.getenv("NAMESPACE", "default")
        print(f'Watching pods in namespace "{namespace}"...')

        resource_version = ""
        while True:
            try:
                # Stream events starting from the latest resource version
                for event in self.k8s_watcher.stream(
                    self.core_api.list_namespaced_pod,
                    namespace,
                    resource_version=resource_version,
                    timeout_seconds=60,
                ):
                    self.handle_pod_event(event)
                    # Save the latest resource version
                    resource_version = event["object"].metadata.resource_version

            except client.rest.ApiException as e:
                if e.status == 410:  # Gone - resource version too old
                    # Reset resource_version to empty to start from latest
                    resource_version = ""
                    print(
                        "Resource version expired, restarting watch with latest version"
                    )
                    continue
                else:
                    print(f"API Exception: {e}")
                    raise
            except Exception as e:
                print(f"Unexpected error: {e}")
                # Add small delay before retry
                import time

                time.sleep(5)

    def watch_policies(self):
        namespace = os.getenv("NAMESPACE", "default")
        print(f'Watching policies in namespace "{namespace}"...')
        for event in self.k8s_watcher.stream(
            self.networking_api.list_namespaced_network_policy, namespace
        ):
            self.handle_policy_event(event)

    def watch_services(self):
        namespace = os.getenv("NAMESPACE", "default")
        print(f'Watching services in namespace "{namespace}"...')
        for event in self.k8s_watcher.stream(
            self.core_api.list_namespaced_service, namespace
        ):
            event_object = event["object"]
            name = event_object.metadata.name
            print(f"Service: {name}")
            raise NotImplementedError("Service events are not yet implemented.")

    def handle_pod_event(self, event):
        # Get the event type.
        event_type = event["type"]
        pod = event["object"]

        # #Irrelevant, since the pod hasn't been assigned a node yet.
        # if event_type == "ADDED":

        # Here, the pod will be assigned to a node. (So we're handling this as a new-pod-event)
        if event_type == "MODIFIED" and pod.spec.node_name:
            pod = Watcher.create_pod_from_pod_event(event)
            self.watchdog.handle_new_pod(pod)
            print(pod)

        elif event_type == "DELETED":
            # Create the corresponding Pod-object from k8s-event.
            pod = Watcher.create_pod_from_pod_event(event)
            print(pod)

            # Handle the removed Pod.
            self.watchdog.handle_removed_pod(pod)

    def handle_policy_event(self, event):
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


if __name__ == "__main__":
    watcher = Watcher()
    watcher.watch_policies()
