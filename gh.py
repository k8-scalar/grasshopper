import sys
from watcher import Watcher
import threading
import subprocess


def is_openstack():
    """
    Checks if the OpenStack command-line client is installed and accessible.

    This function attempts to run the `openstack --version` command to determine
    if the OpenStack CLI is available on the system. If the command executes
    successfully, it returns True. If the command is not found or cannot be
    executed, it returns False.

    Returns:
        bool: True if the OpenStack CLI is installed and accessible, False otherwise.
    """
    try:
        result = subprocess.run(
            ["openstack", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


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

    if distributed:
        print("Running in distributed mode")
        if is_openstack():
            from ostackfiles.add_distributed_gh_rules import add_rpc_rules
            from ostackfiles.credentials import neutron

            master_sg = neutron.list_security_groups(name="masterSG")[
                "security_groups"
            ][0]
            worker_sg = neutron.list_security_groups(name="workerSG")[
                "security_groups"
            ][0]
            add_rpc_rules(neutron, master_sg["id"], worker_sg["id"])

        thread1 = threading.Thread(target=start_kubelet_watch_server)
        thread2 = threading.Thread(target=watch_policies)
        thread3 = threading.Thread(target=watch_services)

        thread1.start()
        thread2.start()
        thread3.start()
    else:
        print("Running in local mode")
        Watcher().watch_all_events()


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


def watch_services():
    """
    Watches for changes in services using the Watcher class.

    This function creates an instance of the Watcher class and calls its
    watch_services method to monitor service changes.
    """
    Watcher().watch_services()


if __name__ == "__main__":
    main()
