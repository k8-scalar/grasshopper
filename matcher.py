from classes import CIDR, LabelSet, Node, Policy
from security_group_module import SecurityGroupModule
from globals import Map


# A class that provides all functionality to actually execute the GrassHopper Algorithm.
class Matcher:
    def __init__(self):
        # the security-group-module used to actually manipulate the SG's.
        self.security_group_module = SecurityGroupModule()

    # functionality to execute algorithm.
    def SG_config_new_pol(pol: Policy) -> None:
        """
        Enables all required VM-level connections allowed by a newly added sub-policy pol

        Args:
            pol (Policy): The policy object containing selection and allowed criteria.

        Returns:
            None
        """
        for n in Map.get(pol.sel).match_nodes:
            if isinstance(pol.allow, CIDR):
                SecurityGroupModule.SG_add_conn(pol, n, None)
            else:
                for m in Map.get(pol.allow).match_nodes:
                    SecurityGroupModule.SG_add_conn(pol, n, m)

    def SG_config_remove_pol(pol: Policy) -> None:
        """
        Conversely removes all VM connections no longer required after removing pol

        Args:
            pol (Policy): The policy object containing the configuration to be removed.

        Returns:
            None
        """
        for n in Map.get(pol.sel).match_nodes:
            if isinstance(pol.allow, CIDR):
                SecurityGroupModule.SG_remove_conn(pol, n, None)
            else:
                for m in Map.get(pol.allow).match_nodes:
                    SecurityGroupModule.SG_remove_conn(pol, n, m)

    def SG_config_new_pod(L: LabelSet, n: Node) -> None:
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
        for pol in Map.get(L).select_pols:
            if isinstance(pol.allow, CIDR):
                SecurityGroupModule.SG_add_conn(pol, n, None)
            else:
                for m in Map.get(pol.allow).match_nodes:
                    SecurityGroupModule.SG_add_conn(pol, n, m)

        for pol in Map.get(L).allow_pols:
            for m in Map.get(pol.allow).match_nodes:
                SecurityGroupModule.SG_add_conn(pol, n, m)

    def SG_config_remove_pod(L: LabelSet, n: Node) -> None:
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
        for pol in Map.get(L).select_pols:
            if isinstance(pol.allow, CIDR):
                SecurityGroupModule.SG_remove_conn(pol, n, None)
            else:
                for m in Map.get(pol.allow).match_nodes:
                    SecurityGroupModule.SG_remove_conn(pol, n, m)

        for pol in Map.get(L).allow_pols:
            for m in Map.get(pol.allow).match_nodes:
                SecurityGroupModule.SG_remove_conn(pol, n, m)