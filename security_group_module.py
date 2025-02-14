from classes import CIDR, Node, Policy, Rule, SecurityGroup, LabelSet
from cluster_state import ClusterState
from helpers import traffic_pols, running
from openstackfiles.openstack_client import OpenStackClient
from abc import ABC, abstractmethod
from openstackfiles.security_group_operations import create_security_group_if_not_exists, attach_security_group_to_instance



class SecurityGroupModule(ABC):

    @staticmethod
    @abstractmethod
    def SGn(n) -> SecurityGroup:
        pass
    
    @staticmethod
    def add_rule_to_remotes(SG: SecurityGroup, rule: Rule) -> None:
        print(
            f"SGMod: Adding rule to {SG.name}, remote {rule.target.name}, port {rule.traffic.port}, type {rule.traffic.direction}"
        )
        neutron = OpenStackClient().get_neutron()
        created_rule = neutron.create_security_group_rule(
            {
                "security_group_rule": {
                    "direction": rule.traffic.direction,
                    "ethertype": "IPv4",
                    "protocol": rule.traffic.protocol,
                    "port_range_min": rule.traffic.port,
                    "port_range_max": rule.traffic.port,
                    "remote_group_id": rule.target.id,
                    "security_group_id": SG.id,
                }
            }
        )
        rule.id = created_rule["security_group_rule"]["id"]
        SG.remotes.add(rule)

    @staticmethod
    def remove_rule_from_remotes(SG: SecurityGroup, rule: Rule) -> None:
        if rule.id is None:
            existing_rules = SG.remotes
            for r in existing_rules:
                if r.target == rule.target and r.traffic == rule.traffic:
                    rule.id = r.id
                    break
            if rule.id is None:
                print(f"SGMod: {rule} not found in {SG.name}")
                print("Existing rules are:")
                for rule in SG.remotes:
                    print(rule)
                return
        print(f"SGMod: Removing rule {rule.id} from {SG.name}")
        neutron = OpenStackClient().get_neutron()
        neutron.delete_security_group_rule(security_group_rule=rule.id)
        # Create a new set without the rule to remove
        SG.remotes = {r for r in SG.remotes if r.id != rule.id}

    @staticmethod
    def rule_from(pol: Policy, m: Node) -> Rule:
        A, traffic = pol.allow[0]
        return Rule(A if isinstance(A, CIDR) else SecurityGroupModule.SGn(m), traffic)


# A class to encompass all functionality of actually manipulating the SG's
# through the Openstack API.
class SecurityGroupModulePNS(SecurityGroupModule):
    @staticmethod
    def SGn(n: Node) -> SecurityGroup:
        return ClusterState().get_security_groups().get("SG_" + n.name)

    @staticmethod
    def SG_add_conn(pol: Policy, n: Node, m: Node) -> None:
        print(f"SGMod: Adding connection from {n.name} to {m.name}")
        rule: Rule = SecurityGroupModule.rule_from(pol, m)
        if rule not in SecurityGroupModulePNS.SGn(n).remotes:
            SecurityGroupModule.add_rule_to_remotes(SecurityGroupModulePNS.SGn(n), rule)

    @staticmethod
    def SG_remove_conn(pol: Policy, n: Node, m: Node) -> None:
        print(f"SGMod: Removing connection from {n.name} to {m.name}")
        if not isinstance(pol.allow[0][0], CIDR):
            if traffic_pols(pol.allow[0][1], n, m) != pol:
                print(
                    f"SGMod: policy has no running traffic from node {n.name} to node {m.name}"
                )
                return
            SecurityGroupModule.remove_rule_from_remotes(
                SecurityGroupModulePNS.SGn(n), SecurityGroupModulePNS.rule_from(pol, m)
            )
            print(f"SGMod: removed rule from {SecurityGroupModulePNS.SGn(n).name}")
            

class SecurityGroupModulePLS(SecurityGroupModule):
    @staticmethod
    def SGn(L: LabelSet) -> str:
        return "SG-" + L.get_string_repr()

    @staticmethod
    def create_security_group(L: LabelSet):
        """
        This method is used to create a security group in openstack.

        Returns: sg_our_model: SecurityGroup | A SecurityGroup object.

        """
        name = SecurityGroupModulePLS.SGn(L)
        description = "Security Group for " + name
        sg = create_security_group_if_not_exists(name, description)
        sg_id = sg["id"]
        sg_name = sg["name"]

        sg_our_model = SecurityGroup(sg_id, sg_name)
        return sg_our_model
    
    
    @staticmethod
    def add_sg(L: LabelSet):
        """
        Method to add a SG. This method creates a security group for the given labelset
        and attaches it to every node, that is running a pod with said labelset. Additionally,
        it adds the created SecurityGroup-object to the ClusterState.
        """
        if SecurityGroupModulePLS.SGn(L) not in ClusterState.get_security_groups():
            sg = SecurityGroupModulePLS.create_security_group(L)
            
            for n in filter(lambda n: running(L, n), ClusterState.get_nodes()):
                SecurityGroupModulePLS.attach_security_group_to_node(sg, n)

            ClusterState.add_security_group(sg)
        

    @staticmethod
    def remove_sg(L: LabelSet):
        """
        This method is used to remove a security group for a given labelset.
        It detaches the security group for the given labelset from all nodes, 
        running on a pod that has those labels.

        Additionally, it removes the security group from the cluster state.

        """
        if SecurityGroupModulePLS.SGn(L) in ClusterState.get_security_groups.keys():
            for n in filter(lambda n: running(L, n), ClusterState.get_nodes()):
                SecurityGroupModulePLS.detach_security_group(sg, n)

            ClusterState.remove_security_group(SecurityGroupModulePLS.SGn(L))

    @staticmethod
    def attach_security_group_to_node(sg: SecurityGroup, node_id: str):
        """
        A method used for attaching a security group to an openstack node.
        """
        nova = OpenStackClient().get_nova()
        server = nova.servers.find(name=node_id)
        security_group_name = sg.name
        sg_id = sg.id

        print(f"Attaching security group {security_group_name} to instance {node_id}")
        server.add_security_group(sg_id)


    @staticmethod
    def detach_security_group(sg: SecurityGroup, node_id: str):
        """
        A method used for detaching a security group from an openstack node.
        """
        nova = OpenStackClient().get_nova()
        server = nova.servers.find(name=node_id)
        security_group_name = sg.name
        sg_id = sg.id

        print(f"Detaching security group {security_group_name} to instance {node_id}")
        server.remove_security_group(sg_id)

    @staticmethod
    def add_rule_to_remotes(sg: SecurityGroup, rule: Rule):
        """
        A method used to add a rule to a given security group.
        """
        try:
            super().add_rule_to_remotes(sg, rule)
        except Exception:
            print("Cannot add rule to remotes (probably already exists...)")

    @staticmethod
    def rule_from(spol: Policy):
        """
        A method to create a security group rule from a given splitted policy.

        Returns:

            rule: Rule | The created rule from the splitted policy.
        """
        A, traffic = spol.allow[0]
        return Rule(A if isinstance(A, CIDR) else ClusterState.get_security_group(SecurityGroupModulePLS.SGn(A)), traffic)