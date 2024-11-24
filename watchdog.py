from classes import Pod, Policy
from helpers import matching, running
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
        print(f"New pod: {pod.name}, on node: {pod.node.name}")

        for label_set in filter(
            lambda L: matching(L, pod), ClusterState.get_label_sets()
        ):
            map_entry = ClusterState.get_map_entry(label_set)
            if map_entry is None or pod.node not in map_entry.matchNodes:
                # 'pod' is the first pod on n to match L
                ClusterState.add_match_node_to_map_entry(label_set, pod.node)
                self.matcher.SG_config_new_pod(label_set, pod.node)

    def handle_modified_pod(self, pod: Pod):
        print(f"Modified pod: {pod.name}, on node: {pod.node.name}")
        pass

    def handle_removed_pod(self, pod: Pod):
        print(f"Removed pod: {pod.name}, on node: {pod.node.name}")

        n = pod.node
        pod.node = None
        for label_set in filter(
            lambda L: matching(L, pod), ClusterState.get_label_sets()
        ):
            if not running(label_set, n):
                ClusterState.remove_match_node_from_map_entry(label_set, n)
                self.matcher.SG_config_remove_pod(label_set, n)
