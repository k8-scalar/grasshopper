import sys


def main():
    if len(sys.argv) != 3:
        print("Usage: gh.py <singleSGPerNodeScenario> <distributed>")
        sys.exit(1)

    singleSGPerNodeScenario = sys.argv[1].lower() == "true"
    distributed = sys.argv[2].lower() == "true"

    if distributed:
        print("Running in distributed mode")
        from ostackfiles.add_distributed_gh_rules import (
            add_rpc_rules_to_master_and_worker_sg,
        )
        from kubelet_watch_server import KubeletWatchServer
        from ostackfiles.credentials import neutron

        master_sg = neutron.list_security_groups(name="masterSG")["security_groups"][0]
        worker_sg = neutron.list_security_groups(name="workerSG")["security_groups"][0]

        add_rpc_rules_to_master_and_worker_sg(neutron, master_sg["id"], worker_sg["id"])
        KubeletWatchServer().start()
    else:
        print("Running in local mode")
        from watcher import Watcher

        Watcher().watch_events()


if __name__ == "__main__":
    main()
