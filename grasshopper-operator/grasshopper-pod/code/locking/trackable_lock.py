
# ==========================================================================================
# ============================ This file is not used anymore ===============================
# ==========================================================================================

import threading

class TrackableLock:
    def __init__(self):
        self._lock = threading.RLock()
        self._owner = None

    def acquire(self):
        self._lock.acquire()
        self._owner = threading.get_ident()

    def release(self):
        self._owner = None
        self._lock.release()

    def is_held_by_current_thread(self):
        return self._owner == threading.get_ident()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
