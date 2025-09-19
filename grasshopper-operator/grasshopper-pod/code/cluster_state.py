from kubernetes import client, config
from classes import *
from openstackfiles.openstack_client import OpenStackClient
import pickle
import os
import datetime
import logging

logger = logging.getLogger(__name__)

# Defining the paths to the NFS share and database.
NFS_PATH = "/mnt/nfs_share/"
DATABASE_PATH           = NFS_PATH      + "cluster_state_persisted/"

# Defining paths to specific parts of the database.
RUNNING_PATH            = DATABASE_PATH + "running.pkl"
LAST_TIME_MODIFIED_PATH = DATABASE_PATH + "last_time_modified.pkl"
PODS_PATH               = DATABASE_PATH + "pods.pkl"
POLICIES_PATH           = DATABASE_PATH + "policies.pkl"
NODES_PATH              = DATABASE_PATH + "nodes.pkl"
SECURITY_GROUPS_PATH    = DATABASE_PATH + "security_groups.pkl"
MAP_PATH                = DATABASE_PATH + "map.pkl"
OFFENDERS_PATH          = DATABASE_PATH + "offenders.pkl"


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

    # Set of all offending policies
    offenders = set()

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ClusterState, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    @staticmethod
    def initialize_cluster_configuration():
        if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
            logging.info("Running inside a Kubernetes Pod. Using in-cluster configuration.")
            config.load_incluster_config()  # Load in-cluster config
        else:
            logging.info("Running locally. Using kubeconfig.")
            config.load_kube_config()  # Load kubeconfig for local development

    @staticmethod
    def read_running_state():
        """ Function to read the running variable from database."""
        
        with open(RUNNING_PATH, "rb") as running_db:
            return pickle.load(running_db)

    @staticmethod
    def load_cluster_state_from_database():
        """ Function used to read the stored cluster state. """

        logging.info("============= INITIALISING CLUSTER STATE FROM DATABASE ==============")

        # Initialising a database dict and filling it with actual database values.
        database = dict()

        with open(RUNNING_PATH, "rb") as running_db:
            database.update({'running': pickle.load(running_db)}) 

        with open(LAST_TIME_MODIFIED_PATH, "rb") as db:
            last_time_modified = pickle.load(db)
            database.update({'last_time_modified': last_time_modified})
        
        with open(PODS_PATH, "rb") as db:
            pods = pickle.load(db)
            database.update({'pods': pods})
        
        with open(POLICIES_PATH, "rb") as db:
            policies = pickle.load(db)
            database.update({'policies': policies})

        with open(NODES_PATH, "rb") as db:
            nodes = pickle.load(db)
            database.update({'nodes': nodes})
        
        with open(MAP_PATH, "rb") as db:
            map_ = pickle.load(db)
            database.update({'map': map_})

        with open(SECURITY_GROUPS_PATH, "rb") as db:
            security_groups = pickle.load(db)
            database.update({'security_groups': security_groups})
        
        with open(OFFENDERS_PATH, "rb") as db:
            offenders = pickle.load(db)
            database.update({'offenders': offenders})

        ClusterState.pods = database["pods"]
        ClusterState.policies = database["policies"]
        ClusterState.nodes = database["nodes"]
        ClusterState.map = database["map"]
        ClusterState.security_groups = database["security_groups"]
        ClusterState.offenders = database["offenders"]

        logging.info(str(ClusterState()))
        logging.info("================== END OF INITIALISATION ===========================")

        return database

    @staticmethod
    def startup(PNS_scenario: bool, namespace):
        """
            Function to start up the the cluster state. It will read the persisted cluster state (database)
            to see if the program was already running or not. Depending on this, it will either load in the 
            stored cluster state, or initialize the cluster state freshly.

        """

        running = ClusterState.read_running_state()

        if running:
            logging.info("Grasshopper was running, initializing cluster state from database.")
            # Add nodes to Cluster State.
            ClusterState.initialize_light(PNS_scenario, namespace)
            ClusterState.load_cluster_state_from_database()
        else:
            logging.info("Grasshopper was not running, initialising Cluster State.")
            ClusterState.initialize(PNS_scenario, namespace)

        ClusterState.set_running_true()


    @staticmethod
    def set_running_true():
        """ 
        Function to set the running-variable to true in the database,
        letting the operator know, the program was running.
        
        """
        with open(RUNNING_PATH, "wb") as running_db:
            pickle.dump(True, running_db)

    @staticmethod
    def initialize(PNS_scenario: bool, namespace):
        """ Function to initialize the cluster state freshly """

        # Import necessary classes.
        from watchdog import WatchDog
        from watcher import Watcher

        # Create Watchdog to handle already existing pods and policies.
        watchdog = WatchDog(PNS_scenario)

        # Create a Kubernetes API client
        v1 = client.CoreV1Api()

        # Set running variable in database, letting the operator know program was running.
        ClusterState.set_running_true()

        # Put nodes in cluster state.
        nodes = v1.list_node().items
        for node in nodes:
            ClusterState.add_node(Node(name=node.metadata.name))

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
    
        logging.info("================================= FRESH INITIALISATION DONE =====================================")

    @staticmethod
    def initialize_light(PNS_scenario: bool, namespace):
        """ Function to initialize the cluster state freshly """

        # Create a Kubernetes API client
        v1 = client.CoreV1Api()

        # Put nodes in cluster state.
        nodes = v1.list_node().items
        for node in nodes:
            ClusterState.add_node(Node(name=node.metadata.name))

        logging.info("================================= LIGHT INITIALISATION DONE (Nodes added)=====================================")

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
        """ Adds an entry to map, also persists the map in database."""

        if label_set in ClusterState().map:
            logging.info("labelset already in map")
        ClusterState().map.update({label_set: map_entry})
        ClusterState().persist_map()

    @staticmethod
    def get_nodes():
        return ClusterState().nodes

    @staticmethod
    def add_node(node: Node):
        ClusterState().nodes.append(node)
        ClusterState().persist_nodes()
    
    @staticmethod
    def get_pods():
        return ClusterState().pods

    @staticmethod
    def get_pods_by_node(node: Node):
        return set(filter(lambda pod: pod.node == node, ClusterState().pods))

    @staticmethod
    def add_pod(pod: Pod):
        ClusterState().pods.append(pod)
        ClusterState.persist_pods()

    @staticmethod
    def remove_pod(pod: Pod):
        ClusterState().pods.remove(pod)
        ClusterState.persist_pods()

    @staticmethod
    def get_policies():
        return ClusterState().policies

    @staticmethod
    def add_policy(pol: Policy):
        ClusterState().policies.append(pol)
        ClusterState.persist_policies()

    @staticmethod
    def remove_policy(pol: Policy):
        ClusterState.policies.remove(pol)
        ClusterState.persist_policies()

    @staticmethod
    def get_offenders():
        return ClusterState.offenders

    @staticmethod
    def add_offender(pol: Policy):
        ClusterState.offenders.add(pol)
        ClusterState.persist_offenders()

    @staticmethod
    def remove_offender(pol: Policy):
        ClusterState.offenders.remove(pol)
        ClusterState.persist_offenders()

    @staticmethod
    def get_map_entry(label_set: LabelSet):
        return ClusterState().map.get(label_set)

    @staticmethod
    def remove_map_entry(label_set: LabelSet):
        """ Function to remove an entry from the map, also persist map to database. """

        logging.info("Removing map entry.")
        if label_set in ClusterState.map:
            ClusterState.map.pop(label_set)
        else:
            logging.info(f"labelset: {label_set} not presented in the map.")
        ClusterState.persist_map()

    @staticmethod
    def add_match_node_to_map_entry(label_set: LabelSet, node: Node):
        """ Function to adapt an entry from the map, also persist map to database. """

        if label_set in ClusterState().map:
            ClusterState().map[label_set].match_nodes.add(node)
        else:
            # Handle the case where the label_set is not in the map
            map_entry = MapEntry()
            map_entry.match_nodes.add(node)
            ClusterState().map[label_set] = map_entry
        
        ClusterState.persist_map()

    @staticmethod
    def remove_match_node_from_map_entry(label_set: LabelSet, node: Node):
        """ Function to adapt an entry from the map, also persist map to database. """

        if label_set in ClusterState().map:
            ClusterState().map[label_set].match_nodes.remove(node)
        else:
            # Handle the case where the label_set is not in the map
            raise Exception("LabelSet not found in the map")
        
        ClusterState.persist_map()

    @staticmethod
    def get_label_sets():
        return ClusterState().map.keys()

    @staticmethod
    def get_security_groups():
        return ClusterState().security_groups

    @staticmethod
    def get_security_group(sg_name: str):
        return ClusterState().security_groups.get(sg_name)

    @staticmethod
    def add_security_group(sg: SecurityGroup):
        """ Function to add a security group to the cluster state, also persist to database. """

        ClusterState().security_groups[sg.name] = sg
        ClusterState.persist_security_groups()

    @staticmethod
    def remove_security_group(sg_name: str):
        """ Function to add a security group to the cluster state, also persist to database. """
        ClusterState().security_groups.pop(sg_name)
        ClusterState.persist_security_groups()

    @staticmethod
    def persist_pods():
        with open(PODS_PATH, "wb") as db:
            pickle.dump(ClusterState().pods, db)
                
    @staticmethod
    def persist_policies():
        with open(POLICIES_PATH, "wb") as db:
            pickle.dump(ClusterState().policies, db)

    @staticmethod
    def persist_nodes():
        with open(NODES_PATH, "wb") as db:
            pickle.dump(ClusterState().nodes, db)

    @staticmethod
    def persist_map():
        with open(MAP_PATH, "wb") as db:
            pickle.dump(ClusterState().map, db)

    @staticmethod
    def persist_security_groups():
        with open(SECURITY_GROUPS_PATH, "wb") as db:
            pickle.dump(ClusterState().security_groups, db)

    @staticmethod
    def persist_offenders():
        with open(OFFENDERS_PATH, "wb") as db:
            pickle.dump(ClusterState().offenders, db)

    @staticmethod
    def clean_database():
        """ Method used to clear the database stored in the NFS share."""

        # Debug statement.
        logging.info("Clearing database.")

        # Actually clearing the database.
        with open(RUNNING_PATH, "wb") as running_db:
            running = False
            pickle.dump(running, running_db)
        
        with open(PODS_PATH, "wb") as db:
            pods = []
            pickle.dump(pods, db)
        
        with open(POLICIES_PATH, "wb") as db:
            policies = []
            pickle.dump(policies, db)

        with open(NODES_PATH, "wb") as db:
            nodes = []
            pickle.dump(nodes, db)
        
        with open(MAP_PATH, "wb") as db:
            map_ = dict()
            pickle.dump(map_, db)

        with open(SECURITY_GROUPS_PATH, "wb") as db:
            security_groups = dict()
            pickle.dump(security_groups, db)
        
        with open(OFFENDERS_PATH, "wb") as db:
            offenders = set()
            pickle.dump(offenders, db)

        with open(LAST_TIME_MODIFIED_PATH, "wb") as db:
            last_time_modified = datetime.datetime.now()
            pickle.dump(last_time_modified, db)
            

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
