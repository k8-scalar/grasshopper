import logging
import pickle
import datetime

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

def set_running_true():
    """ 
    Function to set the running-variable to true in the database,
    letting the operator know, the program was running.
    
    """
    with open(RUNNING_PATH, "wb") as running_db:
        pickle.dump(True, running_db)

    
clean_database()
