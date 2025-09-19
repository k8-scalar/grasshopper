from classes import *
from helpers import matching, running, matching_ls
from matcher import PLSMatcher, PNSMatcher
from cluster_state import ClusterState
from locking.lockmanager2 import LockManager
import threading


class WatchDog:
    def __init__(self, PNS_scenario):
        # PNS_scenario = True
        self.set_matcher(PNS_scenario)
        self.labelSetLockManager = LockManager()

    def set_matcher(self, PNS_scenario: bool):
        """
        Sets the appriopriate matcher.
        """
        if PNS_scenario:
            self.matcher = PNSMatcher()
        else:
            self.matcher = PLSMatcher()

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
            - If it has an allow-rule, which selects all pods. (empty selector or 0.0.0.0/0

            Is only called on splitted policies, so we assume the allow-list has only 1 element.
        """

        if len(spol.sel.labels) == 0:  # empty dict corresponds to empty-selector.
            return True

        if isinstance(spol.allow[0][0], LabelSet):
            if (
                len(spol.allow[0][0].labels) == 0
            ):  # empty dict corresponds to empty-selector.
                return True

        if isinstance(spol.allow[0][0], CIDR):
            if spol.allow[0][0].cidr == "0.0.0.0/0":
                return True

        return False

    # report the policy to offenders. (if not verified)
    def report_policy(self, pol):
        ClusterState.add_offender(pol)

    @staticmethod
    def get_involved_labelsets_from_policy(pol: Policy) -> set[LabelSet]:
        """
        Collects all labelsets that could be affected by this policy:
        - The policy's selector and allow labelset
        - Any other policy that uses the same labelsets
        """
        involved_labelsets = set(pol.get_involved_labelsets())
        return involved_labelsets

    # functions to handle added / removed / modified policies.
    def handle_new_policy(self, pol: Policy):

        # Get all involved labelsets of the policy.
        involved_labelsets = WatchDog.get_involved_labelsets_from_policy(pol)

        # Lock those labelsets.
        print(f"[{threading.get_ident()}] Handling new policy {pol.name}, locking {ClusterState.get_labelsets_string(involved_labelsets)} ...")
        with self.labelSetLockManager.lock_labelsets(involved_labelsets):
            
            # Only handle the new policy once.
            for spol in WatchDog.split(pol):
                if spol in ClusterState().get_policies():
                    print(f"Policy {pol.name} already exists in the cluster.")
                    return

            verified = self.verify_policy(pol)

            if verified:
                for spol in WatchDog.split(pol):
                    WatchDog.add_policy(spol)
                    for node in ClusterState().get_nodes():
                        if running(spol.sel, node):
                            ClusterState().add_match_node_to_map_entry(spol.sel, node)
                    if isinstance(spol.allow[0][0], LabelSet):
                        for node in ClusterState().get_nodes():
                            if running(spol.allow[0][0], node):
                                ClusterState().add_match_node_to_map_entry(
                                    spol.allow[0][0], node
                                )
                    self.matcher.SG_config_new_pol(spol)

                    ClusterState.add_policy(spol)
                print(f"Successfully added policy {pol.name} to ClusterState")
            else:
                print(f"Reporting policy {pol.name}...")
                self.report_policy(pol)

            
        print(f"[{threading.get_ident()}] Handled new policy {pol.name}, Released {ClusterState.get_labelsets_string(involved_labelsets)} ...")
        # print(ClusterState())

    def handle_removed_policy(self, pol: Policy):
        if pol in ClusterState.get_offenders():
            ClusterState.remove_offender(pol)
        else:
            # Get all involved labelsets of the policy.
            involved_labelsets = WatchDog.get_involved_labelsets_from_policy(pol)

            # Lock those labelsets.
            print(f"[{threading.get_ident()}] Handling removed policy {pol.name}, locking {ClusterState.get_labelsets_string(involved_labelsets)} ...")
            with self.labelSetLockManager.lock_labelsets(involved_labelsets):
                for spol in WatchDog.split(pol):
                    try:
                        self.matcher.SG_config_remove_pol(spol)
                        WatchDog.remove_policy(spol)
                        # Also remove policy from ClusterState.policies
                        ClusterState.remove_policy(spol)
                    except:
                        raise Exception(f"Exception in handle_removed_policy")


            print(f"[{threading.get_ident()}] Handled removed policy {pol.name}, Released {ClusterState.get_labelsets_string(involved_labelsets)} ...")

        print("Succesfully removed policy from ClusterState")
        # print(ClusterState())


    # Remove a splitted policy.
    @staticmethod
    def remove_policy(spol):
        s = ClusterState.get_map_entry(spol.sel)
        a = ClusterState.get_map_entry(
            spol.allow[0][0]
        )  # Get labelset from allow-rule.

        s.remove_select_policy(spol)
        a.remove_allow_policy(spol)

        if len(s.select_pols) == 0 and len(s.allow_pols) == 0:
            ClusterState.remove_map_entry(spol.sel)

        if len(a.select_pols) == 0 and len(a.allow_pols) == 0:
            ClusterState.remove_map_entry(spol.allow[0][0])

    @staticmethod
    def add_policy(pol: Policy):  # Adding the policy to ClusterState().
        if not ClusterState().get_map_entry(pol.sel):
            map_entry = MapEntry()
            ClusterState().add_map_entry(pol.sel, map_entry)
        ClusterState().get_map_entry(pol.sel).add_select_policy(pol)

        if not isinstance(pol.allow[0][0], CIDR):
            if not ClusterState().get_map_entry(pol.allow[0][0]):
                map_entry = MapEntry()
                ClusterState().add_map_entry(pol.allow[0][0], map_entry)
            ClusterState().get_map_entry(pol.allow[0][0]).add_allow_policy(pol)

    def handle_modified_policy(self, pol: Policy):
        pass

    @staticmethod
    def get_involved_labelsets(pod: Pod) -> set[LabelSet]:
        """
        Method to get all involved labelsets, while handling a new pod. 
        This includes the labels of the pod itself, all matching labelsets and
        and policies that use those labelsets as a select or allow policy.
        With policies, we mean all labelsets that are used in a policy, either as
        a select or as an allow-rule.
        """
        # Pods own labelset, and all matching labelsets.
        used_labelsets = {pod.label_set}
        used_labelsets.update([ls for ls in ClusterState.get_label_sets() if matching(ls, pod)])

        # Polcies in which the labelsets are used as a select or allow policy.
        involved_pols = set()
        for ls in used_labelsets:
            if ClusterState.get_map_entry(ls):
                involved_pols = involved_pols | ClusterState.get_map_entry(ls).select_pols | ClusterState.get_map_entry(ls).allow_pols
    
        # Labelsets of those policies.
        for pol in involved_pols:
            used_labelsets.update(pol.get_involved_labelsets())

        return used_labelsets

    def handle_new_pod(self, pod: Pod):
        # Get all involved labelsets.
        used_labelsets = WatchDog.get_involved_labelsets(pod)

        # Lock all involved labelsets.
        print(f"[{threading.get_ident()}] Handling pod {pod.name}, locking {ClusterState.get_labelsets_string(used_labelsets)} ...")
        with self.labelSetLockManager.lock_labelsets(used_labelsets):

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
                if map_entry is None or pod.node not in map_entry.match_nodes:
                    # 'pod' is the first pod on n to match L
                    ClusterState().add_match_node_to_map_entry(label_set, pod.node)
                    self.matcher.SG_config_new_pod(label_set, pod.node)
            
        # print(ClusterState())
        print(f"[{threading.get_ident()}] Pod {pod.name} handled. Released locks for: {ClusterState.get_labelsets_string(used_labelsets)}")


    def handle_removed_pod(self, pod: Pod):
        # Only handle removed pod event once.
        if pod not in ClusterState().get_pods():
            print(f"Pod {pod.name} does not exist in the cluster.")
            return

        # Get all involved labelsets.
        used_labelsets = WatchDog.get_involved_labelsets(pod)

        # Lock all involved labelsets.
        print(f"[{threading.get_ident()}] Handling removed pod {pod.name}, locking {ClusterState.get_labelsets_string(used_labelsets)} ...")
        with self.labelSetLockManager.lock_labelsets(used_labelsets):

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
        
        print(f"[{threading.get_ident()}] Handled removed pod {pod.name}, released {ClusterState.get_labelsets_string(used_labelsets)} ...")


        # print(ClusterState())
