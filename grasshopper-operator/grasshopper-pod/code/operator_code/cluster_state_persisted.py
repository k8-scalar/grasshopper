import os 
import pickle
from code.cluster_state import ClusterState
from code.classes import *

NFS_path = "/mnt/nfs_share"

DATABASE_PATH = NFS_path + "/cluster_state_persisted.pkl"

class PersistedClusterState(ClusterState):
    """ Using the Decorator Pattern to make the ClusterState persistent. """

    @staticmethod
    def start_up():
        cs = PersistedClusterState.read_database()
        if cs == {}:
            ClusterState.initialize()
        else:
            ClusterState.pods = cs.pods
            ClusterState.policies cs.policies
            ClusterState.nodes = cs.nodes
            ClusterState.security_groups = cs.security_groups
            ClusterState.map = cs.map

            last_time_modified = cs.last_time_modified

            for event in get_events(last_time_modified):
                watcher.handle_event(event)

    @staticmethod
    def _save():
        with open(DATABASE_PATH, "wb") as cluster_state_persisted_db:
            pickle.dump(ClusterState(), cluster_state_persisted_db)

    @staticmethod
    def read_database():
        with open(DATABASE_PATH, 'rb') as f:
            cluster_state_persisted = pickle.load(f)
            return cluster_state_persisted

    @staticmethod
    def clear_database():
        with open(DATABASE_PATH, 'wb') as f:
            pickle.dump({}, f)

    def add_pod(pod: Pod):
        ClusterState.add_pod(pod)
        PersistedClusterState._save()

    def remove_pod(pod: Pod):
        ClusterState.remove_pod(pod)
        PersistedClusterState._save()


# Defining pods.
pod = Pod("pod-1", {"app": "app-1"}, "worker-1")
pod2 = Pod("pod-2", {"app": "app-1"}, "worker-1")

    
# Clearing the database.
PersistedClusterState.clear_database()


# Adding pods.
PersistedClusterState.add_pod(pod)

cluster_state = PersistedClusterState.read_database()

print(cluster_state)


PersistedClusterState.add_pod(pod2)

cluster_state = PersistedClusterState.read_database()

print(cluster_state)

PersistedClusterState.remove_pod(pod2)

cluster_state = PersistedClusterState.read_database()

print(cluster_state)
            
