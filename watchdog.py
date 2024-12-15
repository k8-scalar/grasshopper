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
        print(pol)

        # if self.verify_policy(pol):
        #     # Update the cluster state.
        #     # should call the matcher object to handle
        #     pass
        # else:
        #     self.report_policy(pol)

    def handle_removed_policy(self, pol: Policy):
        print(pol)

    def handle_modified_policy(self, pol: Policy):
        pass

    # functions to handle added / removed pods.
    def handle_new_pod(self, pod: Pod):
        # Only handle the new pod once.
        if pod in ClusterState().get_pods():
            print(f"Pod {pod.name} already exists in the cluster.")
            return

        print(f"New pod: {pod.name}, on node: {pod.node.name}")
        ClusterState().add_pod(pod)

        for label_set in filter(
            lambda L: matching(L, pod), ClusterState().get_label_sets()
        ):
            map_entry = ClusterState().get_map_entry(label_set)
            if map_entry is None or pod.node not in map_entry.matchNodes:
                # 'pod' is the first pod on n to match L
                ClusterState().add_match_node_to_map_entry(label_set, pod.node)
                self.matcher.SG_config_new_pod(label_set, pod.node)

    def handle_removed_pod(self, pod: Pod):
        # Only handle removed pod event once.
        if pod not in ClusterState().get_pods():
            print(f"Pod {pod.name} does not exist in the cluster.")
            return

        print(f"Removed pod: {pod.name}, on node: {pod.node.name}")
        ClusterState().remove_pod(pod)

        n = pod.node
        pod.node = None
        for label_set in filter(
            lambda L: matching(L, pod), ClusterState().get_label_sets()
        ):
            if not running(label_set, n):
                ClusterState().remove_match_node_from_map_entry(label_set, n)
                self.matcher.SG_config_remove_pod(label_set, n)
