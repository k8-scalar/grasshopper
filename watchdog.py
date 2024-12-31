from classes import *
from helpers import matching, running
from matcher import Matcher
from cluster_state import ClusterState
import copy


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
            sub_pol = Policy(pol_new.name, pol_new.sel, [allow_rule])
            sub_policies.append(sub_pol)

        return sub_policies

    @staticmethod
    def policy_check(pol_new) -> bool:
        policies: set[Policy] = ClusterState().get_policies()
        passed = policies.copy()

        for pol in WatchDog.split(pol_new):
            if WatchDog.conflicting(pol, passed):
                print("Policy check failed, policy is conflicting. Aborting...")
                return False

            if WatchDog.redundant(pol, passed):
                print("Policy check failed, policy is redundant. Aborting...")
                return False     

            if WatchDog.permissive(pol):
                print("Policy check failed, policy is overly permissive. Aborting...")
                return False

            else:
                passed.append(pol)
        return True

    @staticmethod
    def conflicting(pol_new, pols) -> bool:
        for pol in pols:
            if pol_new.sel.issubset(pol.sel):
                for labelset_new, traffic_new in pol_new.allow:
                    if not isinstance(labelset_new, LabelSet):
                        continue
                    for labelset, traffic in pol.allow:
                        if not isinstance(labelset, LabelSet):
                            continue
                        if (
                            traffic_new == traffic
                            and labelset_new.issubset(labelset)
                            and (pol_new.sel != pol.sel or labelset_new != labelset)
                        ):
                            return True
        return False

    @staticmethod
    def redundant(pol_new, pols) -> bool:
        is_redundant = False
        for pol in pols:
            if pol.sel.issubset(pol_new.sel):
                is_redundant = True
                for labelset_new, traffic_new in pol_new.allow:
                    if not isinstance(labelset_new, LabelSet):
                        continue
                    exists_match = False
                    for labelset, traffic in pol.allow:
                        if not isinstance(labelset, LabelSet):
                            continue
                        if traffic_new == traffic and labelset.issubset(labelset_new):
                            exists_match = True
                    if exists_match == False:
                        return False
                return True
        return False

    @staticmethod
    def permissive(spol) -> bool:
        """
        Checks whether or not a given policy is overly permissive.
        I.e.: 
            - It has the empty selector in it's selected-attribute. (Selects all pods)
            - If it has an allow-rule, which selects all pods. (empty selector or 0.0.0.0/24

            Is only called on splitted policies, so we assume the allow-list has only 1 element.
        """

        if len(spol.sel.labels) == 0: # empty dict corresponds to empty-selector. 
            return True

        if isinstance(spol.allow[0][0], LabelSet):
            if len(spol.allow[0][0].labels) == 0: # empty dict corresponds to empty-selector. 
                return True

        if isinstance(spol.allow[0][0], CIDR):
            if spol.allow[0][0].cidr == "0.0.0.0/24":
                return True
                
        return False

    # report the policy to offenders. (if not verified)
    def report_policy(self, pol):
        ClusterState.add_offender(pol)

    # functions to handle added / removed / modified policies.
    def handle_new_policy(self, pol: Policy):
        verified = self.verify_policy(pol)

        if verified:
            print(
                # f"Passed policy check, adding new policy: {pol.name} to cluster state."
            )

            for spol in WatchDog.split(pol):
                WatchDog.add_policy(spol)
                for node in ClusterState().get_nodes():
                    if running(spol.sel, node):
                        ClusterState().add_match_node_to_map_entry(spol.sel, node)
                if isinstance(spol.allow, LabelSet):
                    for node in ClusterState().get_nodes():
                        if running(spol.allow, node):
                            ClusterState().add_match_node_to_map_entry(spol.allow, node)
                # Matcher.SG_config_new_pol(spol)
            
            ClusterState.add_policy(pol)
            print("Succesfully added policy to ClusterState")
        else:
            print("Reporting policy...")
            self.report_policy(pol)

        ClusterState().print()

    def handle_removed_policy(self, pol: Policy):
        if pol in ClusterState.get_offenders():
            ClusterState.remove_offender(pol)
        else:
            for spol in WatchDog.split(pol):
                # self.matcher.SG_config_remove_pol(pol)
                WatchDog.remove_policy(spol)

            # Also remove policy from ClusterState.policies
            ClusterState.remove_policy(pol)
        
        print("Succesfully removed policy from ClusterState")
        ClusterState.print()

    # Remove a splitted policy.
    @staticmethod
    def remove_policy(spol):
        s = ClusterState.get_map_entry(spol.sel)
        a = ClusterState.get_map_entry(spol.allow[0][0]) # Get labelset from allow-rule.

        s.remove_select_policy(spol)
        a.remove_allow_policy(spol)

        if (len(s.select_pols) == 0 and len(s.allow_pols) == 0):
            ClusterState.remove_map_entry(spol.sel)
        
        if (len(a.select_pols) == 0 and len(a.allow_pols) == 0):
            ClusterState.remove_map_entry(spol.allow[0][0])

    @staticmethod
    def add_policy(pol: Policy):  # Adding the policy to ClusterState().
        if not ClusterState().get_map_entry(pol.sel):
            map_entry = MapEntry()
            ClusterState().add_map_entry(pol.sel, map_entry)
        ClusterState().get_map_entry(pol.sel).add_select_policy(pol)

        if not isinstance(pol.allow, CIDR):
            if not ClusterState().get_map_entry(pol.allow[0][0]):
                map_entry = MapEntry()
                ClusterState().add_map_entry(pol.allow[0][0], map_entry)
            ClusterState().get_map_entry(pol.allow[0][0]).add_allow_policy(pol)

    def handle_modified_policy(self, pol: Policy):
        pass

    # functions to handle added / removed / modified pods.
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
