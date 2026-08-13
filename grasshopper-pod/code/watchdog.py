from classes import *
from helpers import matching, running, matching_ls, selector_issubset
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
            sub_pol = Policy(pol_new.name, pol_new.sel, [allow_rule], pol_new.namespace)
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
            if selector_issubset(pol_new.sel, pol.sel):
                for labelset_new, traffic_new in pol_new.allow:
                    if not isinstance(labelset_new, LabelSet):
                        continue
                    for labelset, traffic in pol.allow:
                        if not isinstance(labelset, LabelSet):
                            continue
                        if (
                            traffic_new == traffic
                            and selector_issubset(labelset_new, labelset)
                            and (pol_new.sel != pol.sel or labelset_new != labelset)
                        ):
                            return True
        return False

    @staticmethod
    def redundant(pol_new, pols) -> bool:
        is_redundant = False
        for pol in pols:
            if selector_issubset(pol.sel, pol_new.sel):
                is_redundant = True
                for labelset_new, traffic_new in pol_new.allow:
                    if not isinstance(labelset_new, LabelSet):
                        continue
                    exists_match = False
                    for labelset, traffic in pol.allow:
                        if not isinstance(labelset, LabelSet):
                            continue
                        if traffic_new == traffic and selector_issubset(labelset, labelset_new):
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
            - It has the empty selector in it's selected-attribute. (Selects all pods
              in the policy's own namespace - sel has no discretionary namespace scope,
              so this check is unconditional regardless of namespace.)
            - If it has an allow-rule, which selects all pods in all namespaces
              (empty pod-labels AND no namespace restriction) or 0.0.0.0/0.
              An allow-rule with empty pod-labels but a real namespace restriction
              (e.g. "any pod in this one namespace") is a legitimate, narrower
              pattern and is NOT considered overly permissive.

            Is only called on splitted policies, so we assume the allow-list has only 1 element.
        """

        if len(spol.sel.labels) == 0:  # empty dict corresponds to empty-selector.
            return True

        if isinstance(spol.allow[0][0], LabelSet):
            allow_labelset = spol.allow[0][0]
            if len(allow_labelset.labels) == 0 and not allow_labelset.namespace_labels:
                # empty pod-labels AND no (or empty) namespace restriction = any pod, any namespace.
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
        s.remove_select_policy(spol)
        if len(s.select_pols) == 0 and len(s.allow_pols) == 0:
            ClusterState.remove_map_entry(spol.sel)

        # A CIDR allow-peer (ipBlock) never gets a map entry in the first
        # place (see add_policy) - nothing to remove it from here either.
        if isinstance(spol.allow[0][0], CIDR):
            return

        a = ClusterState.get_map_entry(spol.allow[0][0])  # Get labelset from allow-rule.
        a.remove_allow_policy(spol)
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

    def handle_new_namespace(self, name: str, labels: dict[str, str]):
        """
        Registers a namespace's labels, so namespaceSelector-based policies can
        match against it. Best-effort: if a namespace's labels change later
        (handle_new_namespace called again with updated labels), already-computed
        SG rules that depended on the old labels are NOT retroactively
        re-evaluated - same rigor level as handle_modified_policy above.
        """
        ClusterState.add_namespace(name, labels)

    def handle_removed_namespace(self, name: str):
        ClusterState.remove_namespace(name)

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


    def handle_new_pods_batch(self, pods: set[Pod]):
        """
        Batch equivalent of handle_new_pod() for a whole group of untracked
        pods at once - e.g. everything a reconciliation pass finds missing
        from ClusterState in one sweep. Computes the eventual (labelset,
        node) SG configuration needed for the WHOLE group in memory first,
        then locks and applies it ONCE, instead of paying a separate lock
        acquisition (and the contention that implies under a burst - many
        pods sharing the same labelset all fight over the same lock) for
        every individual pod.

        This changes nothing about WHAT gets computed - SG_config_new_pod is
        already deduped per (labelset, node) pair inside handle_new_pod (a
        second pod landing on an already-covered node never re-triggers it),
        so N pods converge to the exact same end state either way. This only
        changes HOW MANY TIMES a lock gets acquired to get there: once per
        labelset here, instead of once per pod. Confirmed live: a 1000-pod
        burst processed one-pod-at-a-time stalled for many minutes under
        exactly this lock contention, compounded by a slow OpenStack call
        holding a lock that hundreds of unrelated pods were all waiting on.
        """
        pods = {pod for pod in pods if pod not in ClusterState().get_pods()}
        if not pods:
            return

        # Which existing labelsets does each pod in the batch newly match,
        # and which of those (labelset, node) pairs aren't covered yet.
        by_labelset: dict[LabelSet, set[Pod]] = {}
        for label_set in ClusterState.get_label_sets():
            for pod in pods:
                if matching(label_set, pod):
                    by_labelset.setdefault(label_set, set()).add(pod)

        involved_labelsets = {pod.label_set for pod in pods} | set(by_labelset)
        involved_pols = set()
        for ls in involved_labelsets:
            entry = ClusterState.get_map_entry(ls)
            if entry:
                involved_pols |= entry.select_pols | entry.allow_pols
        for pol in involved_pols:
            involved_labelsets.update(pol.get_involved_labelsets())

        print(f"[{threading.get_ident()}] Handling batch of {len(pods)} new pod(s), locking {ClusterState.get_labelsets_string(involved_labelsets)} ...")
        with self.labelSetLockManager.lock_labelsets(involved_labelsets):
            for pod in pods:
                if pod in ClusterState().get_pods():
                    continue
                print(f"New pod: {pod.name}, on node: {pod.node.name}")
                ClusterState().add_pod(pod)

            for label_set, matched_pods in by_labelset.items():
                map_entry = ClusterState().get_map_entry(label_set)
                new_nodes = {pod.node for pod in matched_pods} - map_entry.match_nodes
                for node in new_nodes:
                    # 'node' is the first node in this batch to match label_set.
                    ClusterState().add_match_node_to_map_entry(label_set, node)
                    self.matcher.SG_config_new_pod(label_set, node)

        print(f"[{threading.get_ident()}] Batch of {len(pods)} new pod(s) handled. Released locks for: {ClusterState.get_labelsets_string(involved_labelsets)}")

    def handle_removed_pods_batch(self, pods: set[Pod]):
        """
        Batch equivalent of handle_removed_pod() for a whole group of
        currently-tracked pods that no longer exist, all at once - see
        handle_new_pods_batch's docstring for why this matters under a burst.

        Removes every pod from ClusterState FIRST, then checks running() (the
        reference-count guard) once per (labelset, node) pair rather than
        once per pod - correct because it's checking against the batch's
        final post-removal state directly, rather than N sequential
        snapshots that would have reached the same conclusion anyway just
        with more redundant lock/check cycles along the way.
        """
        pods = {pod for pod in pods if pod in ClusterState().get_pods()}
        if not pods:
            return

        involved_labelsets = set()
        for pod in pods:
            involved_labelsets.update(WatchDog.get_involved_labelsets(pod))

        print(f"[{threading.get_ident()}] Handling batch of {len(pods)} removed pod(s), locking {ClusterState.get_labelsets_string(involved_labelsets)} ...")
        with self.labelSetLockManager.lock_labelsets(involved_labelsets):
            affected_nodes_by_labelset: dict[LabelSet, set[Node]] = {}
            for pod in pods:
                if pod not in ClusterState().get_pods():
                    continue
                print(f"Removed pod: {pod.name}, on node: {pod.node.name}")
                ClusterState().remove_pod(pod)
                n = pod.node
                pod.node = None
                for label_set in filter(lambda L: matching(L, pod), ClusterState().get_label_sets()):
                    affected_nodes_by_labelset.setdefault(label_set, set()).add(n)

            for label_set, nodes in affected_nodes_by_labelset.items():
                for node in nodes:
                    if not running(label_set, node):
                        ClusterState().remove_match_node_from_map_entry(label_set, node)
                        self.matcher.SG_config_remove_pod(label_set, node)

        print(f"[{threading.get_ident()}] Batch of {len(pods)} removed pod(s) handled. released {ClusterState.get_labelsets_string(involved_labelsets)} ...")

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
