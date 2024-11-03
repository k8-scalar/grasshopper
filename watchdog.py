from classes import Pod, Policy
from matcher import Matcher


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
            # should call the matcher object to handle
            pass
        else:
            self.report_policy(pol)

    def handle_modified_policy(pod: Pod):
        pass

    def handle_removed_policy(pod: Pod):
        pass

    # functions to handle added / removed / modified pods.
    def handle_new_pod(pod: Pod):
        pass

    def handle_modified_pod(pod: Pod):
        pass

    def handle_removed_pod(pod: Pod):
        pass
