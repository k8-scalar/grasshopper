from kubernetes import client, config
from classes import *
from is_openstack import is_openstack
import os
from openstackfiles.openstack_client import OpenStackClient
from locking.lockmanager import LockManager


# Implements Singleton Pattern.
class ClusterState:

    # Mapping of label sets to their corresponding map entries
    map: dict[LabelSet, MapEntry] = {}

    # Set of all nodes in the cluster
    nodes: set[Node] = []

    # Set of all pods in the cluster
    pods: set[Pod] = []

    # Set of all policies in the cluster
    policies: set[Policy] = []

    # Mapping of security group names to their corresponding security group objects
    security_groups: dict[str, SecurityGroup] = {}

    # Mapping of namespace name to that namespace's own labels
    namespaces: dict[str, dict[str, str]] = {}

    # Set of all offending policies
    offenders = set()

    _instance = None

    _labelSetLockManager = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ClusterState, cls).__new__(cls, *args, **kwargs)
            cls._labelSetLockManager = LockManager()
        return cls._instance

    @staticmethod
    def initialize_cluster_configuration():
        if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
            print("Running inside a Kubernetes Pod. Using in-cluster configuration.")
            config.load_incluster_config()  # Load in-cluster config
        else:
            print("Running locally. Using kubeconfig.")
            config.load_kube_config()  # Load kubeconfig for local development

    @staticmethod 
    def initialize_security_groups(PNS_scenario: bool):
        # necessary to make PNS-variant work.
        if PNS_scenario:
            from openstackfiles.openstack_client import OpenStackClient

            neutron = OpenStackClient().get_neutron()
            security_groups = neutron.list_security_groups()["security_groups"]
            for sg in security_groups:
                security_group = SecurityGroup(name=sg["name"], id=sg["id"])
                rules_json = sg["security_group_rules"]
                rules = [
                    Rule(
                        target=security_group,
                        traffic=Traffic(
                            direction=rule["direction"],
                            port=rule["port_range_min"],  # TODO: handle port_range_max
                            protocol=rule["protocol"],
                        ),
                    )
                    for rule in rules_json
                ]
                security_group.remotes = set(rules)
                ClusterState().security_groups[sg["name"]] = security_group


    @staticmethod
    def initialize(PNS_scenario: bool, namespace):
        """ Function to initialize the cluster state."""
        
        # local imports to avoid circular imports.
        from watchdog import WatchDog
        from watcher import Watcher

        # Create Watchdog to handle already existing pods and policies.
        watchdog = WatchDog(PNS_scenario)

        # Create a Kubernetes API client
        v1 = client.CoreV1Api()

        # Put nodes in cluster state.
        nodes = v1.list_node().items
        for node in nodes:
            ClusterState.add_node(Node(name=node.metadata.name))

        # Put namespaces in cluster state (needed before any pod/policy is matched
        # against a namespaceSelector).
        for ns in v1.list_namespace().items:
            ClusterState.add_namespace(ns.metadata.name, ns.metadata.labels or {})

        # Handle already existing pods.
        pods = v1.list_namespaced_pod(namespace).items
        for pod in pods:
            pod = Watcher.create_pod_from_pod_object(pod)
            watchdog.handle_new_pod(pod)
        
        # Handle already created network policies.
        networking_v1 = client.NetworkingV1Api()
        k8s_policies = networking_v1.list_namespaced_network_policy(namespace).items

        for policy_object in k8s_policies:
            policy = Watcher.create_policy_from_policy_object(policy_object)
            watchdog.handle_new_policy(policy)

        
        ClusterState.initialize_security_groups(PNS_scenario)

        print("================================= FRESH INITIALISATION DONE =====================================")

    @staticmethod
    def initialize_light(PNS_scenario: bool, namespace=None):
        """ Function to initialize the cluster state. `namespace` is unused here
        (kept for backward compatibility with callers that still pass it) - pods
        and policies are populated later via kopf resume handlers, cluster-wide."""
        
        # local imports to avoid circular imports.
        from watchdog import WatchDog
        from watcher import Watcher

        # Create Watchdog to handle already existing pods and policies.
        watchdog = WatchDog(PNS_scenario)

        # Create a Kubernetes API client
        v1 = client.CoreV1Api()

        # Put nodes in cluster state.
        nodes = v1.list_node().items
        for node in nodes:
            ClusterState.add_node(Node(name=node.metadata.name))

        # Put namespaces in cluster state (synchronously, before kopf dispatches any
        # pod/policy resume handler that could otherwise race ahead of namespace data).
        for ns in v1.list_namespace().items:
            ClusterState.add_namespace(ns.metadata.name, ns.metadata.labels or {})

        ClusterState.initialize_security_groups(PNS_scenario)

        print("================================= FRESH (Light) INITIALISATION DONE =====================================")


    @staticmethod
    def get_labelsets_string(labelsets: set[LabelSet]):
        labelsets_string = ""
        for l in labelsets:
            labelsets_string += l.get_string_repr() + ", "
        
        return labelsets_string

    @staticmethod
    def get_map():
        return ClusterState().map

    @staticmethod
    def add_map_entry(label_set: LabelSet, map_entry: MapEntry):
        if label_set in ClusterState().map:
            print("labelset already in map")
        ClusterState().map.update({label_set: map_entry})

    @staticmethod
    def get_nodes():
        return ClusterState().nodes

    @staticmethod
    def add_node(node: Node):
        ClusterState().nodes.append(node)

    @staticmethod
    def get_pods():
        return ClusterState().pods

    @staticmethod
    def get_pods_by_node(node: Node):
        return set(filter(lambda pod: pod.node == node, ClusterState().pods))

    @staticmethod
    def add_pod(pod: Pod):
        ClusterState().pods.append(pod)

    @staticmethod
    def remove_pod(pod: Pod):
        ClusterState().pods.remove(pod)

    @staticmethod
    def get_policies():
        return ClusterState().policies

    @staticmethod
    def add_policy(pol: Policy):
        ClusterState().policies.append(pol)

    @staticmethod
    def remove_policy(pol: Policy):
        if pol in ClusterState.policies:
            ClusterState.policies.remove(pol)
        else: 
            raise Exception(f"Policy not in ClusterState.policies !")

    @staticmethod
    def get_offenders():
        return ClusterState.offenders

    @staticmethod
    def add_offender(pol: Policy):
        ClusterState.offenders.add(pol)

    @staticmethod
    def remove_offender(pol: Policy):
        ClusterState.offenders.remove(pol)

    @staticmethod
    def get_map_entry(label_set: LabelSet):
        return ClusterState().map.get(label_set)

    @staticmethod
    def remove_map_entry(label_set: LabelSet):
        print("Removing map entry.")
        if label_set in ClusterState.map:
            ClusterState.map.pop(label_set)
        else:
            print(f"labelset: {label_set} not presented in the map.")

    @staticmethod
    def add_match_node_to_map_entry(label_set: LabelSet, node: Node):
        if label_set in ClusterState().map:
            ClusterState().map[label_set].match_nodes.add(node)
        else:
            # Handle the case where the label_set is not in the map
            map_entry = MapEntry()
            map_entry.match_nodes.add(node)
            ClusterState().map[label_set] = map_entry

    @staticmethod
    def remove_match_node_from_map_entry(label_set: LabelSet, node: Node):
        if label_set in ClusterState().map:
            ClusterState().map[label_set].match_nodes.remove(node)
        else:
            # Handle the case where the label_set is not in the map
            raise Exception("LabelSet not found in the map")

    @staticmethod
    def get_label_sets():
        return ClusterState().map.keys()

    @staticmethod
    def get_namespace_labels(name: str) -> dict[str, str]:
        """
        Returns the known labels of namespace `name`. Falls back to just the
        auto-injected kubernetes.io/metadata.name label if the namespace hasn't
        been registered yet (e.g. a resume race, or missing Namespace RBAC) -
        this keeps the common "same namespace" case working even without full
        Namespace watch data; namespaceSelectors on custom labels degrade
        gracefully (no match) until the real data arrives.
        """
        return ClusterState().namespaces.get(name, {"kubernetes.io/metadata.name": name})

    @staticmethod
    def add_namespace(name: str, labels: dict[str, str]):
        ClusterState().namespaces[name] = labels or {}

    @staticmethod
    def remove_namespace(name: str):
        ClusterState().namespaces.pop(name, None)

    @staticmethod
    def get_security_groups():
        return ClusterState().security_groups

    @staticmethod
    def get_security_group(sg_name: str):
        return ClusterState().security_groups.get(sg_name)

    @staticmethod
    def add_security_group(sg: SecurityGroup):
        ClusterState().security_groups[sg.name] = sg

    @staticmethod
    def remove_security_group(sg_name: str):
        ClusterState().security_groups.pop(sg_name)

    def __str__(self):
        result = ["--------------", "Cluster State:"]

        result.append("Nodes:")
        if self.nodes:
            for node in self.nodes:
                result.append(f"  - {node}")
        else:
            result.append("  None")

        result.append("\nPods:")
        if self.pods:
            for pod in self.pods:
                result.append(f"  - {pod}")
        else:
            result.append("  None")

        result.append("\nPolicies:")
        if self.policies:
            for policy in self.policies:
                result.append(f"  - {policy}")
        else:
            result.append("  None")

        result.append("\nOffending Policies:")
        if self.offenders:
            for policy in self.offenders:
                result.append(f"  - {policy}")
        else:
            result.append("  None")

        result.append("\nNamespaces:")
        if self.namespaces:
            for name, labels in self.namespaces.items():
                result.append(f"  - {name}: {labels}")
        else:
            result.append("  None")

        result.append("\nSecurity Groups:")
        if self.security_groups:
            for name, sg in self.security_groups.items():
                result.append(f"  - {name}: {sg}")
        else:
            result.append("  None")

        result.append("\nLabel Sets to Map Entries:")
        if self.map:
            for label_set, map_entry in self.map.items():
                result.append(f"  - {label_set}: {map_entry}")
        else:
            result.append("  None")

        result.append("--------------")
        return "\n".join(result)
