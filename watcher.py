from kubernetes import watch, client, config
from watchdog import WatchDog


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
        Handles Pod events based on their type (ADDED, DELETED, MODIFIED).

    handle_policy_event(event):
        Handles NetworkPolicy events based on their type (ADDED, DELETED, MODIFIED).

    handle_service_event(event):
        Handles Service events based on their type (ADDED, DELETED, MODIFIED).
    """

    def __init__(self):
        self.load_config()
        self.watchdog = WatchDog()
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
        print("Watching events now...")
        for event in self.k8s_watcher.stream(
            self.core_api.list_event_for_all_namespaces
        ):
            event_object = event["object"]
            involved_object = event_object.involved_object
            event_kind = involved_object.kind or "Unknown"
            event_type = event.get("type", "Unknown")
            object_name = involved_object.name or "Unknown"
            change_reason = event_object.reason or "Unknown"
            change_reason_message = event_object.message or "No message"
            event_occurred_at = event_object.last_timestamp or "Unknown time"

            print(
                f"Event: {event_kind:>10.10} {object_name:>20.20} {event_type:>10.10} | Reason: {change_reason:>20.20}, {change_reason_message:>90.90} | Occurred at: {event_occurred_at}"
            )

            if event_kind == "Pod":
                self.handle_pod_event(event)
            elif event_kind == "NetworkPolicy":
                self.handle_policy_event(event)
            elif event_kind == "Service":
                self.handle_service_event(event)

    def watch_policies(self):
        print("Watching policies now...")
        for event in self.k8s_watcher.stream(
            self.networking_api.list_network_policy_for_all_namespaces
        ):
            event_object = event["object"]
            name = event_object.metadata.name
            print(f"Policy: {name}")
            # involved_object = event_object.involved_object
            # event_kind = involved_object.kind or "Unknown"
            # event_type = event.get("type", "Unknown")
            # object_name = involved_object.name or "Unknown"
            # change_reason = event_object.reason or "Unknown"
            # change_reason_message = event_object.message or "No message"
            # event_occurred_at = event_object.last_timestamp or "Unknown time"

            # print(
            #     f"Event: {event_kind:>10.10} {object_name:>20.20} {event_type:>10.10} | Reason: {change_reason:>20.20}, {change_reason_message:>90.90} | Occurred at: {event_occurred_at}"
            # )

            # if event_kind == "NetworkPolicy":
            #     self.handle_policy_event(event)

    def watch_services(self):
        print("Watching services now...")
        for event in self.k8s_watcher.stream(
            self.core_api.list_service_for_all_namespaces
        ):
            event_object = event["object"]
            name = event_object.metadata.name
            print(f"Service: {name}")
            # involved_object = event_object.involved_object
            # event_kind = involved_object.kind or "Unknown"
            # event_type = event.get("type", "Unknown")
            # object_name = involved_object.name or "Unknown"
            # change_reason = event_object.reason or "Unknown"
            # change_reason_message = event_object.message or "No message"
            # event_occurred_at = event_object.last_timestamp or "Unknown time"

            # print(
            #     f"Event: {event_kind:>10.10} {object_name:>20.20} {event_type:>10.10} | Reason: {change_reason:>20.20}, {change_reason_message:>90.90} | Occurred at: {event_occurred_at}"
            # )

            # if event_kind == "Service":
            #     self.handle_service_event(event)

    def handle_pod_event(self, event):
        event_type = event["type"]
        if event_type == "ADDED":
            self.watchdog.handle_new_pod(event)
            pass
        elif event_type == "DELETED":
            pass
        elif event_type == "MODIFIED":
            pass

    def handle_policy_event(self, event):
        event_type = event["type"]
        if event_type == "ADDED":
            pass
        elif event_type == "DELETED":
            pass
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


if __name__ == "__main__":
    watcher = Watcher()
    watcher.watch_all_events()
