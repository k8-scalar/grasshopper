from classes import CIDR, LabelSet, Node, Policy
from cluster_state import ClusterState
from security_group_module import SecurityGroupModulePNS, SecurityGroupModulePLS
from abc import ABC, abstractmethod


class Matcher(ABC):

    def __init__(self):
        self.set_security_group_module()

    """
    Defines an interface of a Matcher Class.
    """

    @abstractmethod
    def set_security_group_module(self):
        pass

    @abstractmethod
    def SG_config_new_pol(self, spol):
        pass

    @abstractmethod
    def SG_config_new_pod(self, L, n):
        pass

    @abstractmethod
    def SG_config_remove_pol(self, spl):
        pass

    @abstractmethod
    def SG_config_remove_pod(self, L, n):
        pass


# A class that provides all functionality to actually execute the GrassHopper Algorithm.
class PNSMatcher(Matcher):

    def set_security_group_module(self):
        self.security_group_module = SecurityGroupModulePNS()

    # functionality to execute algorithm.
    def SG_config_new_pol(self, pol: Policy) -> None:
        """
        Enables all required VM-level connections allowed by a newly added sub-policy pol

        Args:
            pol (Policy): The policy object containing selection and allowed criteria.

        Returns:
            None
        """
        mapping = ClusterState().get_map()
        for n in mapping.get(pol.sel).match_nodes:
            if isinstance(pol.allow[0][0], CIDR):
                SecurityGroupModulePNS.SG_add_conn(pol, n, None)
            else:
                for m in mapping.get(pol.allow[0][0]).match_nodes:
                    SecurityGroupModulePNS.SG_add_conn(pol, n, m)

    def SG_config_remove_pol(self, pol: Policy) -> None:
        """
        Conversely removes all VM connections no longer required after removing pol

        Args:
            pol (Policy): The policy object containing the configuration to be removed.

        Returns:
            None
        """
        mapping = ClusterState().get_map()
        for n in mapping.get(pol.sel).match_nodes:
            if isinstance(pol.allow[0][0], CIDR):
                SecurityGroupModulePNS.SG_remove_conn(pol, n, None)
            else:
                for m in mapping.get(pol.allow[0][0]).match_nodes:
                    SecurityGroupModulePNS.SG_remove_conn(pol, n, m)

    def SG_config_new_pod(self, L: LabelSet, n: Node) -> None:
        """
        Adds connections after deploying a new Pod on a Node n, taking into account
        deployed Kubernetes Network Policies that select label set L or contain L in
        their allow section

        Args:
            L (LabelSet): The label set used to select and allow policies.
            n (Node): The node to be configured in the security group.

        Returns:
            None
        """

        print("Configuring new SG for new pod")

        mapping = ClusterState().get_map()
        for pol in mapping.get(L).select_pols:
            if isinstance(pol.allow[0][0], CIDR):
                SecurityGroupModulePNS.SG_add_conn(pol, n, None)
            else:
                for m in mapping.get(pol.allow[0][0]).match_nodes:
                    SecurityGroupModulePNS.SG_add_conn(pol, n, m)

        for pol in mapping.get(L).allow_pols:
            for m in mapping.get(pol.sel).match_nodes:
                SecurityGroupModulePNS.SG_add_conn(pol, m, n)

    def SG_config_remove_pod(self, L: LabelSet, n: Node) -> None:
        """
        Removes connections due to deployed Kubernetes NPs with select or allow sections matching L, after removing a Pod from a Node n

        Args:
            L (LabelSet): The label set containing the policies.
            n (Node): The node to be removed from the security group configuration.

        Note:
            - For `select_pols`, if the policy's `allow` attribute is a `CIDR`, it directly removes the connection.
            Otherwise, it iterates through the nodes matched by the policy's `allow` attribute and removes the connection.
            - For `allow_pols`, it iterates through the nodes matched by the policy's `allow` attribute and removes the connection.
        """
        mapping = ClusterState().get_map()
        for pol in mapping.get(L).select_pols:
            if isinstance(pol.allow[0][0], CIDR):
                SecurityGroupModulePNS.SG_remove_conn(pol, n, None)
            else:
                for m in mapping.get(pol.allow[0][0]).match_nodes:
                    SecurityGroupModulePNS.SG_remove_conn(pol, n, m)

        for pol in mapping.get(L).allow_pols:
            for m in mapping.get(pol.sel).match_nodes:
                SecurityGroupModulePNS.SG_remove_conn(pol, m, n)


class PLSMatcher(Matcher):

    def set_security_group_module(self):
        self.security_group_module = SecurityGroupModulePLS()

    def SG_config_new_pol(self, spol):
        print("PLS implementation...")

        if len(ClusterState.get_map_entry(spol.sel).match_nodes) > 0:
            SecurityGroupModulePLS.add_sg(spol.sel)

            if isinstance(spol.allow[0][0], LabelSet):
                SecurityGroupModulePLS.add_sg(spol.allow[0][0])

            sg = ClusterState.get_security_group(SecurityGroupModulePLS.SGn(spol.allow[0][0]))
            rule = SecurityGroupModulePLS.rule_from(spol)

            SecurityGroupModulePLS.add_rule_to_remotes(sg, rule)

    def SG_config_new_pod(self, L, n):
        print("PLS implementation...")

        for spol in [spol in ClusterState.get_map_entry(L).select_pols] + [spol in ClusterState.get_map_entry(L).allow_pols]:
            PLSMatcher.SG_config_new_pol(spol)
        
        sg = ClusterState.get_security_group(SecurityGroupModulePLS.SGn(L))
        if sg:
            SecurityGroupModulePLS.attach_security_group_to_node(sg, n)

    #TODO: Figure out if-statements
    def SG_config_remove_pol(self, spol):
        print("PLS implementation...")
        sg = ClusterState.get_security_group(SecurityGroupModulePLS.SGn(spol.sel))
        rule = SecurityGroupModulePLS.rule_from(spol)

        if ClusterState.get_map().get(spol.sel) == "...":
            SecurityGroupModulePLS.remove_sg(spol.sel)

        if ClusterState.get_map().get(spol.allow[0][0]) == "...":
            SecurityGroupModulePLS.remove_sg(spol.allow[0][0])


    def SG_config_remove_pod(self, L, n):
        print("PLS implementation...")
        sg = ClusterState.get_security_group(SecurityGroupModulePLS.SGn(L))
        if sg:
            SecurityGroupModulePLS.detach_security_group(sg, n)
