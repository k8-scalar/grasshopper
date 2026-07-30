from kubernetes import watch, client, config
from watchdog import WatchDog
from classes import *
import kopf


class Watcher:
    def __init__(self, PNS_scenario):
        print("Watcher class for Kopf Operator!")
        self.watchdog = WatchDog(PNS_scenario)


    def handle_pod_event(self, event_type, pod_dict):
        pod_name = pod_dict.get("metadata", {}).get("name")
        node_name = pod_dict.get("spec", {}).get("nodeName")

        if event_type == "MODIFIED" and node_name:
            pod = Watcher.create_pod_from_pod_dict(pod_dict)
            print(f"Handling new pod (MODIFIED) on node {node_name}: {pod_name}")
            self.watchdog.handle_new_pod(pod)

        elif event_type == "DELETED":
            pod = Watcher.create_pod_from_pod_dict(pod_dict)
            print(f"Handling pod deletion: {pod_name}")
            self.watchdog.handle_removed_pod(pod)

    def handle_policy_event(self, event_type, policy_dict):
        policy = Watcher.create_policy_from_policy_dict(policy_dict)
        if event_type == "ADDED":
            self.watchdog.handle_new_policy(policy)
        elif event_type == "DELETED":
            self.watchdog.handle_removed_policy(policy)
        elif event_type == "MODIFIED":
            pass  # Optional: implement update handling if needed

    def handle_service_event(self, event_type, service_dict):
        if event_type == "ADDED":
            pass
        elif event_type == "DELETED":
            pass
        elif event_type == "MODIFIED":
            pass

    @staticmethod
    def create_pod_from_pod_dict(obj: dict) -> Pod:
        metadata = obj.get("metadata", {})
        spec = obj.get("spec", {})

        name = metadata.get("name")
        namespace = metadata.get("namespace")
        labels = metadata.get("labels", {})
        node_name = spec.get("nodeName")

        label_set = LabelSet(labels)
        node = Node(node_name) if node_name else None

        return Pod(name, label_set, node, namespace)

    @staticmethod
    def create_policy_from_policy_dict(obj: dict) -> Policy:
        metadata = obj.get("metadata", {})
        spec = obj.get("spec", {})

        name = metadata.get("name")
        namespace = metadata.get("namespace")
        pod_selector = spec.get("podSelector", {})
        ingress = spec.get("ingress", [])
        egress = spec.get("egress", [])

        match_labels = pod_selector.get("matchLabels", {})
        selected = Watcher.create_selected(match_labels, namespace)

        allow_list = []
        if ingress:
            allow_list += Watcher.create_allow_list_ingress(ingress, namespace)
        if egress:
            allow_list += Watcher.create_allow_list_egress(egress, namespace)

        return Policy(name, selected, allow_list, namespace)

    @staticmethod
    def create_allow_list_ingress(ingress_list, policy_namespace):
        allow_list = []
        for ingress in ingress_list:
            from_entries = ingress.get("from", [])
            ports = ingress.get("ports", [])

            for entry in from_entries:
                labelset = Watcher.parse_networkpolicypeer_field(entry, policy_namespace)
                for port in ports:
                    traffic = Traffic(INGRESS, port.get("port"), port.get("protocol"))
                    allow_list.append((labelset, traffic))
        return allow_list

    @staticmethod
    def create_allow_list_egress(egress_list, policy_namespace):
        allow_list = []
        for egress in egress_list:
            to_entries = egress.get("to", [])
            ports = egress.get("ports", [])

            for entry in to_entries:
                labelset = Watcher.parse_networkpolicypeer_field(entry, policy_namespace)
                for port in ports:
                    traffic = Traffic(EGRESS, port.get("port"), port.get("protocol"))
                    allow_list.append((labelset, traffic))
        return allow_list

    @staticmethod
    def parse_networkpolicypeer_field(entry: dict, policy_namespace: str) -> LabelSet | CIDR:
        if "ipBlock" in entry:
            return CIDR(str(entry["ipBlock"].get("cidr")))

        pod_labels = entry.get("podSelector", {}).get("matchLabels", {})

        if "namespaceSelector" in entry:
            # Explicit namespaceSelector present: restricts to namespaces whose own
            # labels match (empty matchLabels / empty namespaceSelector = any namespace).
            namespace_labels = entry["namespaceSelector"].get("matchLabels", {})
        else:
            # No namespaceSelector: podSelector (if any) implicitly means "in the
            # policy's own namespace", per k8s NetworkPolicyPeer semantics.
            namespace_labels = {"kubernetes.io/metadata.name": policy_namespace}

        return LabelSet(pod_labels, namespace_labels)

    @staticmethod
    def create_selected(label_set: dict[str, str], policy_namespace: str) -> LabelSet:
        # A policy's own podSelector always implicitly means "in its own namespace".
        return LabelSet(label_set, {"kubernetes.io/metadata.name": policy_namespace})

    @staticmethod
    def create_namespace_from_dict(obj: dict) -> tuple[str, dict[str, str]]:
        metadata = obj.get("metadata", {})
        return metadata.get("name"), metadata.get("labels", {})
