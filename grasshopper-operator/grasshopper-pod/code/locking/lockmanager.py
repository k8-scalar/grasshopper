import threading
from collections import defaultdict
from contextlib import contextmanager
from classes import LabelSet, Policy
from locking.trackable_lock import TrackableLock

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
                cls._instance._labelset_locks = defaultdict(TrackableLock)
                cls._instance._global_lock = threading.Lock()
            return cls._instance


    def acquire_resource(self, resource: LabelSet | Policy):
        if isinstance(resource, LabelSet):
            return self.acquire_labelset(resource)

        if isinstance(resource, Policy):
            return self.lock_policy(resource)

    def release_resource(self, resource: LabelSet | Policy):
        if isinstance(resource, LabelSet):
            return self.release_labelset(resource)

        if isinstance(resource, Policy):
            return self.unlock_policy(resource)

    def _get_lock(self, labelset: LabelSet) -> threading.RLock:
        """
        Function to get a lock from the locks-dictionary. It will automatically create one and store it, 
        if it does not yet exist. 
        """

        key = labelset.get_string_repr()
        with self._global_lock:
            return self._labelset_locks[key]

    def acquire_labelset(self, labelset: LabelSet):
        """
        Function to acquire a lock for a given labelset.
        """
        lock = self._get_lock(labelset)
        if not lock.is_held_by_current_thread():
            lock.acquire()
        else:
            print(f"Acquire Exception: Lock for labelset: {labelset} is already acquired by this thread!")

        # print(f"[{threading.get_ident()}] LOCKS: {str(self._labelset_locks)}")

    def release_labelset(self, labelset: LabelSet):
        """
        Function to release a lock for a given labelset.
        """

        lock = self._get_lock(labelset)
        if lock.is_held_by_current_thread():
            lock.release()
        else:
            print(f"Release Exception: Lock for labelset: {labelset} is not being held by this thread!")

        # print(f"[{threading.get_ident()}] LOCKS: {str(self._labelset_locks)}")

    def lock_policy(self, pol: Policy):
        """
        Method to lock a given policy. This method locks all the labelsets that are involved in a policy.
        """
        involved_labelset = {pol.sel}
        involved_labelset.update([rule[0] for rule in pol.allow])

        self.acquire_multiple(involved_labelset)

    def unlock_policy(self, pol: Policy):
        """
        Method to release a given policy. This method releases all the labelsets that are involved in a policy.
        """
        involved_labelset = {pol.sel}
        involved_labelset.update([rule[0] for rule in pol.allow])

        self.release_multiple(involved_labelset)

    @contextmanager
    def locked(self, resource: LabelSet | Policy):
        """
        Context manager for locking a labelset.
        """
        self.acquire_resource(resource)
        try:
            yield
        finally: 
            self.release_resource(resource)

    def acquire_multiple(self, resources: set[LabelSet | Policy]):
        """
        Function to acquire multiple labelsets. It acquires the per-labelset locks in a sorted fasion,
        in order to avoid deadlocks.
        """
        labelsets: set[LabelSet] = set()
        for res in resources:
            if isinstance(res, LabelSet):
                labelsets.add(res)
            elif isinstance(res, Policy):
                labelsets.add(res.sel)
                labelsets.update([rule[0] for rule in res.allow if isinstance(rule[0], LabelSet)])

        for labelset in sorted(labelsets, key=lambda l: l.get_string_repr()):
            self.acquire_labelset(labelset)

    def release_multiple(self, resources: set[LabelSet | Policy]):
        """
        Function to release multiple labelsets. It releases the per-labelset locks in a  (reversed) sorted fasion,
        in order to avoid deadlocks.
        """
        
        labelsets: set[LabelSet] = set()
    
        for res in resources:
            if isinstance(res, LabelSet):
                labelsets.add(res)
            elif isinstance(res, Policy):
                labelsets.add(res.sel)
                labelsets.update([rule[0] for rule in res.allow if isinstance(rule[0], LabelSet)])

        for labelset in sorted(labelsets, key=lambda l: l.get_string_repr(), reverse=True):
            self.release_labelset(labelset)

    @contextmanager
    def locked_multiple(self, resources: set[LabelSet | Policy]):
        """
        Context manager to lock multiple labelsets.
        """
        self.acquire_multiple(resources)
        try:
            yield
        finally:
            self.release_multiple(resources)

    