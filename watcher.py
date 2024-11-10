from kubernetes import watch, client, config
from watchdog import WatchDog


# This is a class used to watch a kubernetes-api-server.
class Watcher:
    def __init__(self):
        self.load_config()
        self.watchdog = WatchDog()
        self.core_v1 = client.CoreV1Api()
        self.networking_v1 = client.NetworkingV1Api()
        self.k8s_watcher: watch.Watch = watch.Watch()

    def load_config(self):
        config.load_kube_config()

    # The main loop to watch all kubernetes events.
    def watch_events(self):
        print("Watching events now...")
        for event in self.k8s_watcher.stream(
            self.core_v1.list_event_for_all_namespaces
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
    watcher.watch_events()
