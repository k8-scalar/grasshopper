from kubernetes import client, config
from classes import *
from is_openstack import is_openstack


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

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ClusterState, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    @staticmethod
    def initialize():
        # Load the Kubernetes configuration
        config.load_kube_config()

        # Create a Kubernetes API client
        v1 = client.CoreV1Api()

        # Get all nodes
        nodes = v1.list_node().items
        for node in nodes:
            ClusterState.nodes.append(Node(name=node.metadata.name))

        # Get all pods
        pods = v1.list_pod_for_all_namespaces().items
        for pod in pods:
            node_name = pod.spec.node_name
            node = next((n for n in ClusterState.nodes if n.name == node_name), None)
            if node:
                ClusterState.pods.append(
                    Pod(
                        name=pod.metadata.name,
                        label_set=LabelSet(labels=pod.metadata.labels),
                        node=node,
                    )
                )

        # Get all policies (assuming policies are represented as NetworkPolicies)
        v1_network = client.NetworkingV1Api()
        policies = v1_network.list_network_policy_for_all_namespaces().items
        for policy in policies:
            # Extract the select set (pod selector)
            select_labels = policy.spec.pod_selector.match_labels
            select_set = LabelSet(labels=select_labels)

            # Extract the allow set (ingress rules)
            if policy.spec.ingress:
                for ingress in policy.spec.ingress:
                    if ingress._from:
                        for from_rule in ingress._from:
                            if from_rule.pod_selector:
                                allow_labels = from_rule.pod_selector.match_labels
                                for port in ingress.ports:
                                    allow_tuple = (
                                        LabelSet(labels=allow_labels),
                                        Traffic(
                                            direction="ingress",
                                            port=port.port,
                                            protocol=port.protocol,
                                        ),
                                    )

                                    # Append the policy to the ClusterState
                                    ClusterState.policies.append(
                                        Policy(
                                            name=policy.metadata.name,
                                            sel=select_set,
                                            allow=allow_tuple,
                                        )
                                    )

            # Extract the allow set (egress rules)
            if policy.spec.egress:
                for egress in policy.spec.egress:
                    for to_rule in egress.to:
                        if to_rule.pod_selector:
                            allow_labels = to_rule.pod_selector.match_labels
                            for port in egress.ports:
                                allow_tuple = (
                                    LabelSet(labels=allow_labels),
                                    Traffic(
                                        direction="egress",
                                        port=port.port,
                                        protocol=port.protocol,
                                    ),
                                )

                                # Append the policy to the ClusterState
                                ClusterState.policies.append(
                                    Policy(
                                        name=policy.metadata.name,
                                        sel=select_set,
                                        allow=allow_tuple,
                                    )
                                )

        # Initialize security groups from OpenStack
        if is_openstack():
            from openstack.openstack_client import OpenStackClient

            neutron = OpenStackClient.get_neutron()
            security_groups = neutron.list_security_groups()["security_groups"]
            for sg in security_groups:
                ClusterState.security_groups[sg["name"]] = SecurityGroup(
                    name=sg["name"], id=sg["id"]
                )

    @staticmethod
    def get_map():
        return ClusterState.map

    @staticmethod
    def add_map_entry(label_set: LabelSet, map_entry: MapEntry):
        ClusterState.map.update({label_set: map_entry})

    @staticmethod
    def get_nodes():
        return ClusterState.nodes

    @staticmethod
    def add_node(node: Node):
        ClusterState.nodes.append(node)

    @staticmethod
    def get_pods():
        return ClusterState.pods

    @staticmethod
    def get_pods_by_node(node: Node):
        return set(filter(lambda pod: pod.node == node, ClusterState.pods))

    @staticmethod
    def add_pod(pod: Pod):
        ClusterState.pods.append(pod)

    @staticmethod
    def get_policies():
        return ClusterState.policies

    @staticmethod
    def add_policy(pol: Policy):
        ClusterState.policies.append(pol)

    @staticmethod
    def get_map_entry(label_set: LabelSet):
        return ClusterState.map.get(label_set)

    @staticmethod
    def add_match_node_to_map_entry(label_set: LabelSet, node: Node):
        if label_set in ClusterState.map:
            ClusterState.map[label_set].matchNodes.add(node)
        else:
            # Handle the case where the label_set is not in the map
            ClusterState.map[label_set] = MapEntry(matchNodes={node})

    @staticmethod
    def remove_match_node_from_map_entry(label_set: LabelSet, node: Node):
        if label_set in ClusterState.map:
            ClusterState.map[label_set].matchNodes.remove(node)
        else:
            # Handle the case where the label_set is not in the map
            raise Exception("LabelSet not found in the map")

    @staticmethod
    def get_label_sets():
        return ClusterState.map.keys()

    @staticmethod
    def get_security_groups():
        return ClusterState.security_groups

    # print out a nice / clear representation of the cluster state.
    @staticmethod
    def print():
        print("--------------")
        print("Cluster State:")

        print("Nodes:")
        if ClusterState.nodes:
            for node in ClusterState.nodes:
                print(f"  - {node}")
        else:
            print("  None")

        print("\nPods:")
        if ClusterState.pods:
            for pod in ClusterState.pods:
                print(f"  - {pod}")
        else:
            print("  None")

        print("\nPolicies:")
        if ClusterState.policies:
            for policy in ClusterState.policies:
                print(f"  - {policy}")
        else:
            print("  None")

        print("\nSecurity Groups:")
        if ClusterState.security_groups:
            for name, sg in ClusterState.security_groups.items():
                print(f"  - {name}: {sg}")
        else:
            print("  None")

        print("\nLabel Sets to Map Entries:")
        if ClusterState.map:
            for label_set, map_entry in ClusterState.map.items():
                print(f"  - {label_set}: {map_entry}")
        else:
            print("  None")

        print("--------------")
