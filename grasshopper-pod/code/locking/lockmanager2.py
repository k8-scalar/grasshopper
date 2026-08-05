import threading
from collections import defaultdict
from contextlib import contextmanager


class LockManager:
    """
    This is per-labelset lock manager class, using the Singleton pattern. 
    This class is used as a manager for acquiring and releasing per-labelset locks,
    throughout the entire program.
    """
    
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._locks = defaultdict(threading.Lock)
                cls._instance._global_lock = threading.Lock()
            return cls._instance

    def _get_lock(self, key: str) -> threading.RLock:
        with self._global_lock:
            return self._locks[key]

    @contextmanager
    def acquire_multiple(self, keys: list[str]):
        """
        Acquire multiple locks in a globally sorted order to avoid deadlocks.
        Locks are re-entrant.
        """
        sorted_keys = sorted(set(keys))
        acquired = []

        try:
            for key in sorted_keys:
                lock = self._get_lock(key)
                lock.acquire()
                acquired.append(lock)
            yield
        finally:
            for lock in reversed(acquired):
                lock.release()


    def lock_labelsets(self, labelsets: list):
        """
        Context manager to lock a list of LabelSets. A CIDR peer (ipBlock) may
        also appear in this list - it never gets a ClusterState.map entry, so
        it needs no lock and is skipped rather than given a lock key.
        """
        lock_keys = [ls.get_string_repr() for ls in labelsets if hasattr(ls, "get_string_repr")]
        return LockManager().acquire_multiple(lock_keys)


    def lock_policy(self, policy):
        """
        Context manager to lock all LabelSets involved in a Policy.
        This includes the select LabelSet and all allowed LabelSets (skipping
        any CIDR/ipBlock allow-peer, which needs no lock - see lock_labelsets).
        """
        labelsets = [policy.sel] + [ls for (ls, _) in policy.allow]
        lock_keys = [ls.get_string_repr() for ls in labelsets if hasattr(ls, "get_string_repr")]
        return LockManager().acquire_multiple(lock_keys)


    def lock_multiple_policies(self, policies: list):
        """
        Context manager to lock all LabelSets involved in multiple Policies.
        All select and allow LabelSets are collected and locked in a globally sorted manner.
        This prevents deadlocks. Any CIDR/ipBlock allow-peer is skipped - see lock_labelsets.
        """
        labelsets = []
        for policy in policies:
            labelsets.append(policy.sel)
            labelsets.extend([ls for (ls, _) in policy.allow])

        lock_keys = [ls.get_string_repr() for ls in labelsets if hasattr(ls, "get_string_repr")]
        return LockManager().acquire_multiple(lock_keys)