from kubernetes import watch, client, config
from watchdog import WatchDog


# This is a class used to watch a kubernetes-api-server.
class Watcher:
    def __init__(self):
        self.watchdog = WatchDog()
        self.core_v1 = client.CoreV1Api()
        self.networking_v1 = client.NetworkingV1Api()
        self.k8s_watcher: watch.Watch = watch.Watch()
        self.load_config

    def load_config():
        config.load_kube_config()

    # The main loop to watch all kubernetes events.
    def watch_events(self):
        print("Watching events now...")
        for event in self.k8s_watcher.stream(self.core_v1.list_namespace):
            event_object = event["object"]
            event_kind = event_object.involved_object.kind

            if event_kind == "Pod":
                self.handle_pod_event(event)
            if event_kind == "NetworkPolicy":
                self.handle_policy_event(event)
            if event_kind == "Service":
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
