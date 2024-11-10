import sys

from kubelet_watch_server import KubeletWatchServer
from watcher import Watcher


def main():
    if len(sys.argv) != 3:
        print("Usage: gh.py <singleSGPerNodeScenario> <distributed>")
        sys.exit(1)

    singleSGPerNodeScenario = sys.argv[1].lower() == "true"
    distributed = sys.argv[2].lower() == "true"

    if distributed:
        print("Running in distributed mode")
        KubeletWatchServer().start()
    else:
        print("Running in local mode")
        Watcher().watch_events()


if __name__ == "__main__":
    main()
