import sys
from cluster_state import ClusterState
from is_openstack import is_openstack
from openstackfiles.create_sg_per_node import create_sg_per_node
from watcher import Watcher
import threading


def main():
    """
    Main function to run the script.

    This function expects two command-line arguments:
    1. <singleSGPerNodeScenario>: A boolean value (true/false) indicating if a single security group per node scenario is used.
    2. <distributed>: A boolean value (true/false) indicating if the script should run in distributed mode.

    If the distributed mode is enabled, it will:
    - If running on OpenStack, it will add RPC rules to the security groups.
    - Start three threads to watch kubelet, policies, and services.

    If the distributed mode is not enabled, it will:
    - Start watching all events using the Watcher class.

    Usage:
        gh.py <singleSGPerNodeScenario> <distributed>
    """
    if len(sys.argv) != 3:
        print("Usage: gh.py <singleSGPerNodeScenario> <distributed>")
        sys.exit(1)

    singleSGPerNodeScenario = sys.argv[1].lower() == "true"
    distributed = sys.argv[2].lower() == "true"

    if singleSGPerNodeScenario:
        create_sg_per_node(delete_existing_rules=True)

    if distributed:
        print("Running in distributed mode")

        if not singleSGPerNodeScenario:
            print("PLS not supported in distributed mode")
            return
        
        print("Running PNS mode")

        if is_openstack():
            print("Running on OpenStack")
            from openstackfiles.add_distributed_gh_rules import add_rpc_rules
            from openstackfiles.openstack_client import OpenStackClient

            neutron = OpenStackClient().get_neutron()

            master_sg = neutron.list_security_groups(name="masterSG")[
                "security_groups"
            ][0]
            worker_sg = neutron.list_security_groups(name="workerSG")[
                "security_groups"
            ][0]
            add_rpc_rules(master_sg["id"], worker_sg["id"])
        else:
            print("Not running on OpenStack")

        ClusterState().initialize()
        print(ClusterState())

        thread1 = threading.Thread(target=start_kubelet_watch_server)
        thread2 = threading.Thread(target=watch_policies)
        # thread3 = threading.Thread(target=watch_services)

        thread1.start()
        thread2.start()
        # thread3.start()
    
    # Running non-distributed.
    else:
        print("Running in local mode")

        # PLS-scenario
        if not singleSGPerNodeScenario:
            print("Running in PLS-mode...")
            ClusterState().initialize()
            policies_PLS_thread = threading.Thread(target=watch_policies_PLS)
            pods_PLS_thread = threading.Thread(target=watch_pods_PLS)

            policies_PLS_thread.start()
            pods_PLS_thread.start()
        
        # PNS-scenario
        else:
            print("Running in PNS-mode...")

            create_sg_per_node(delete_existing_rules=True)

            ClusterState().initialize()

            policies_thread = threading.Thread(target=watch_policies)
            pods_thread = threading.Thread(target=watch_pods)

            policies_thread.start()
            pods_thread.start()


def start_kubelet_watch_server():
    """
    Starts the Kubelet Watch Server.

    This function imports the KubeletWatchServer class from the kubelet_watch_server module
    and starts an instance of the KubeletWatchServer.
    """
    from kubelet_watch_server import KubeletWatchServer

    KubeletWatchServer().start()


def watch_policies():
    """
    Watches for changes in policies using the Watcher class.

    This function creates an instance of the Watcher class and calls its
    watch_policies method to monitor policy changes.
    """
    Watcher().watch_policies()


def watch_pods():
    Watcher().watch_pods()


def watch_services():
    """
    Watches for changes in services using the Watcher class.

    This function creates an instance of the Watcher class and calls its
    watch_services method to monitor service changes.
    """
    Watcher().watch_services()

def watch_policies_PLS():
    Watcher(PNS_scenario=False).watch_policies()

def watch_pods_PLS():
    Watcher(PNS_scenario=False).watch_pods()


if __name__ == "__main__":
    main()
