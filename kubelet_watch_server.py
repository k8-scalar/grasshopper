from xmlrpc.server import SimpleXMLRPCServer
from watchdog import WatchDog
from classes import Pod

master_ip = "0.0.0.0"
master_port = 9000


class KubeletWatchServer:

    def __init__(self):
        self.watchdog: WatchDog = WatchDog()

    def start(self):
        """
        Starts the XML-RPC server to listen for connections from workers.

        This method initializes and starts an instance of `SimpleXMLRPCServer`
        that listens on the specified `master_ip` and `master_port`. It registers
        a function to handle worker connections and registers all methods of the
        `watchdog` instance to the server. The server runs indefinitely, handling
        incoming XML-RPC requests.
        """
        print("Kubeletwatch server started")

        with SimpleXMLRPCServer(
            (master_ip, master_port), logRequests=False, allow_none=True
        ) as server:

            @server.register_function
            def on_connect_worker(text):
                print(f"Worker connected: {text}")
                return True

            @server.register_function
            def handle_new_pod(pod: dict):
                pod = Pod.from_dict(pod)
                self.watchdog.handle_new_pod(pod)

            @server.register_function
            def handle_removed_pod(pod: dict):
                pod = Pod.from_dict(pod)
                self.watchdog.handle_removed_pod(pod)

            server.serve_forever()


if __name__ == "__main__":
    KubeletWatchServer().start()
