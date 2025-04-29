from watcher import Watcher

RESULTS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../experiments/latency/results/handle-times/")

class WatcherWithTiming(Watcher):

    def watch_pods(self):
        print(f"Watching pods now in namespace {self.namespace} ... (and timing handle-times)")
        for event in self.k8s_watcher.stream(
            self.core_api.list_namespaced_pod, namespace=self.namespace
        ):
            self.handle_pod_event(event)