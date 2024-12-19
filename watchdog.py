from classes import *
from helpers import matching, running
from matcher import Matcher
from cluster_state import ClusterState


class WatchDog:
    def __init__(self):
        self.matcher: Matcher = Matcher()

    # verify new policy
    def verify_policy(self, pol: Policy):
        return self.policy_check(pol)

    @staticmethod
    def split(pol_new) -> list[Policy]:
        sub_policies: list[Policy] = []
        for allow_rule in pol_new.allow:
            sub_pol = Policy(pol_new.name, pol_new.sel, allow_rule)
            sub_policies.append(sub_pol)

        return sub_policies

    @staticmethod
    def policy_check(pol_new) -> bool:
        passed: set[Policy] = ClusterState.get_policies()

        for pol in WatchDog.split(pol_new):
            if WatchDog.permissive(pol_new) or WatchDog.conflicting(pol, passed) or WatchDog.redundant(pol, passed):
                print("Policy check failed. Aborting...")
                return False
            else:
                passed.append(pol)
        return True

    @staticmethod
    def conflicting(pol_new, pols) -> bool:
        for pol in ClusterState.get_policies():
            if pol_new.sel.issubset(pol):
                for labelset_new, traffic_new in pol_new.allow:
                    for labelset, traffic in pol.allow:
                        if (traffic_new == traffic and labelset_new.issubset(labelset) and
                            (pol_new.sel != pol.sel or label_set_new != label_set)):
                                return True
        return False

    @staticmethod
    def redundant(pol_new, pols) -> bool:
        is_redundant = False
        for pol in ClusterState.get_policies():
            if pol.sel.issubset(pol_new.sel):
                is_redundant = True
                for labelset_new, traffic_new in pol_new.allow:
                    exists_match = False
                    for labelset, traffic in pol.allow:
                        if traffic_new == traffic and labelset.issubset(label_set_new):
                            exists_match = True
                    if exists_match == False:
                        return False
                return True
        return False

    @staticmethod
    def permissive(pol) -> bool:
        return False

    # report the policy to offenders. (if not verified)
    def report_policy(self, pol):
        pass
    
    # functions to handle added / removed / modified policies.
    def handle_new_policy(self, pol: Policy):
        print(pol)

<<<<<<< Updated upstream
<<<<<<< Updated upstream
        # if self.verify_policy(pol):
        #     # Update the cluster state.
        #     # should call the matcher object to handle
        #     pass
        # else:
        #     self.report_policy(pol)

=======
=======
>>>>>>> Stashed changes
        if self.verify_policy(pol):
            # Update the cluster state.
            # should call the matcher object to handle
            print(f"Passed policy check, adding new policy: {pol.name} to cluster state.")

            # for spol in WatchDog.split(pol):
            #     WatchDog.add_policy(spol)
            # for node in ClusterState.get_nodes():
            #     if running(spol.sel, node):
            #         ClusterState.add_match_node_to_map_entry(spol.sel, node)
            # if isinstance(spol.allow, Labelset):
            #     for node in ClusterState.get_nodes():
            #         if running(spol.allow, node):
            #             ClusterState.add_match_node_to_map_entry(spol.allow, node)
        else:
            self.report_policy(pol)
    
>>>>>>> Stashed changes
    def handle_removed_policy(self, pol: Policy):
        print(pol)

    def handle_modified_policy(self, pol: Policy):
        pass

<<<<<<< Updated upstream
<<<<<<< Updated upstream
    # functions to handle added / removed pods.
=======
    @staticmethod
    def add_policy(pol: Policy): #Adding the policy to ClusterState.
=======
    @staticmethod
    def add_policy(pol: Policy): #Adding the policy to ClusterState.
        pass

    # functions to handle added / removed / modified pods.
    def handle_new_pod(self, pod: Pod):
        #Only handle the new pod once.
        # if pod in ClusterState.get_pods():
        #     return

        print(f"New pod: {pod.name}, on node: {pod.node.name}")
        # ClusterState.add_pod(pod)
        # ClusterState.print()

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
>>>>>>> Stashed changes
        pass

    # functions to handle added / removed / modified pods.
>>>>>>> Stashed changes
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
