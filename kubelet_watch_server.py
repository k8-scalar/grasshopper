from xmlrpc.server import SimpleXMLRPCServer

from watchdog import WatchDog

master_ip = "192.168.1.51"
master_port = 9000


class KubeletWatchServer:

    def __init__(self):
        self.watchdog: WatchDog = WatchDog()

    def start(self):
        with SimpleXMLRPCServer(
            (master_ip, master_port), logRequests=False, allow_none=True
        ) as server:

            @server.register_function
            def on_connect_worker(text):
                print(text)
                return True

            # Registers all methods of the `watchdog` instance.
            server.register_instance(self.watchdog)

            server.serve_forever()


if __name__ == "__main__":
    KubeletWatchServer().start()
