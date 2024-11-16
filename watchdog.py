from classes import Pod, Policy
from matcher import Matcher
from cluster_state import ClusterState


class WatchDog:
    def __init__(self):
        self.matcher: Matcher = Matcher()

    # verify new policy
    def verify_policy(self, pol: Policy):
        pass

    # report the policy to offenders. (if not verified)
    def report_policy(self, pol):
        pass

    # functions to handle added / removed / modified policies.
    def handle_new_policy(self, pol: Policy):
        if self.verify_policy(pol):
            # Update the cluster state.
            # should call the matcher object to handle
            pass
        else:
            self.report_policy(pol)

    def handle_modified_policy(self, pod: Pod):
        pass

    def handle_removed_policy(self, pod: Pod):
        pass

    # functions to handle added / removed / modified pods.
    def handle_new_pod(self, pod: Pod):
        print(f"New pod: {pod}")
        pass

    def handle_modified_pod(self, pod: Pod):
        print(f"Modified pod: {pod}")
        pass

    def handle_removed_pod(self, pod: Pod):
        print(f"Removed pod: {pod}")
        pass
