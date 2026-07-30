from classes import CIDR, Node, Policy, Rule, SecurityGroup, LabelSet, Traffic
from cluster_state import ClusterState
from helpers import traffic_pols, running
from openstackfiles.openstack_client import OpenStackClient
from abc import ABC, abstractmethod
from openstackfiles.security_group_operations import create_security_group_if_not_exists, attach_security_group_to_instance
from locking.lockmanager2 import LockManager
import network_mode
import threading



class SecurityGroupModule(ABC):

    lockmanager = LockManager()

    @staticmethod
    @abstractmethod
    def SGn(n) -> SecurityGroup:
        pass
    
    @staticmethod
    def add_rule_to_remotes(SG: SecurityGroup, rule: Rule) -> None:
        if isinstance(rule.target, CIDR):
            remote = {"remote_ip_prefix": rule.target.cidr}
            target_desc = rule.target.cidr
        else:
            remote = {"remote_group_id": rule.target.id}
            target_desc = rule.target.name

        print(
            f"SGMod: Adding rule to {SG.name}, remote {target_desc}, port {rule.traffic.port}, type {rule.traffic.direction}"
        )
        # A rule always lives in its owning SG's own project - that's exactly why
        # a CIDR target (no ownership constraint) is used for cross-project peers
        # instead of remote_group_id (which Neutron only allows within one project).
        neutron = OpenStackClient.for_project(SG.project).get_neutron()
        try:
            created_rule = neutron.create_security_group_rule(
                {
                    "security_group_rule": {
                        "direction": rule.traffic.direction,
                        "ethertype": "IPv4",
                        "protocol": rule.traffic.protocol,
                        "port_range_min": rule.traffic.port,
                        "port_range_max": rule.traffic.port,
                        **remote,
                        "security_group_id": SG.id,
                    }
                }
            )
            rule.id = created_rule["security_group_rule"]["id"]
            SG.remotes.add(rule)
        except Exception as e:
            raise Exception(f"There was a problem adding rule: {rule} to SG: {SG.name} ({SG.id})\n {e}")

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
        neutron = OpenStackClient.for_project(SG.project).get_neutron()
        try:
            print(f"Removing rule: {rule} form security group: {SG.name} ({SG.id})")
            neutron.delete_security_group_rule(security_group_rule=rule.id)
            # Create a new set without the rule to remove
            SG.remotes = {r for r in SG.remotes if r.id != rule.id}

        except Exception as e:
            raise Exception(f"There was a problem with removing rule: {rule} from SG: {SG.name} ({SG.id})\n {e}")

# A class to encompass all functionality of actually manipulating the SG's
# through the Openstack API.
class SecurityGroupModulePNS(SecurityGroupModule):
    @staticmethod
    def SGn(n: Node) -> SecurityGroup:
        return ClusterState().get_security_groups().get("SG_" + n.name)

    @staticmethod
    def SG_add_conn(pol: Policy, n: Node, m: Node) -> None:
        if n == m:
            print(f"SGMod: Cannot add connection from {n.name} to itself in PNS mode.")
            return
        print(f"SGMod: Adding connection from {n.name} to {m.name}")
        rule: Rule = SecurityGroupModulePNS.rule_from(pol, n, m)
        if rule not in SecurityGroupModulePNS.SGn(n).remotes:
            SecurityGroupModule.add_rule_to_remotes(SecurityGroupModulePNS.SGn(n), rule)

    @staticmethod
    def SG_remove_conn(pol: Policy, n: Node, m: Node) -> None:
        print(f"SGMod: Removing connection from {n.name} to {m.name}")
        if not isinstance(pol.allow[0][0], CIDR):
            if traffic_pols(pol.allow[0][1], n, m) != pol:
                print(
                    f"SGMod: similar traffic for other policy detected from node {n.name} to node {m.name}"
                )
                return
            SecurityGroupModule.remove_rule_from_remotes(
                SecurityGroupModulePNS.SGn(n), SecurityGroupModulePNS.rule_from(pol, n, m)
            )
            print(f"SGMod: removed rule from {SecurityGroupModulePNS.SGn(n).name}")

    @staticmethod
    def rule_from(pol: Policy, n: Node, m: Node) -> Rule:
        """
        Builds the Rule for the connection n -> m allowed by pol. The target
        (SG reference vs CIDR) and traffic (real port vs VXLAN port) depend on
        whether n and m are in the same OpenStack project - see network_mode.py
        and the rule-shape table in the design doc for this feature.
        """
        A, traffic = pol.allow[0]
        if isinstance(A, CIDR):
            return Rule(A, traffic)

        # Resolve the canonical Node instances - n/m as passed in may be disposable
        # ad hoc instances (e.g. built fresh from a pod event) that never carry a
        # real project/internal_ip.
        n_canon = ClusterState.get_node(n.name) or n
        m_canon = ClusterState.get_node(m.name) or m

        if n_canon.project != m_canon.project:
            # Cross-project: remote_group_id is not permitted across OpenStack
            # projects, and this traffic is VXLAN-tunneled regardless of any
            # setting - only the peer's real Node IP and the VXLAN port are ever
            # visible to OpenStack's security-group enforcement at this hop.
            if not m_canon.internal_ip:
                raise Exception(
                    f"Cannot build cross-project rule to node {m_canon.name}: no internal_ip known for it."
                )
            return Rule(CIDR(f"{m_canon.internal_ip}/32"), SecurityGroupModulePNS._vxlan_traffic(traffic))

        if network_mode.intra_project_encapsulation == network_mode.ENCAPSULATION_VXLAN:
            # Same project, but Calico itself is VXLAN-encapsulated: remote_group_id
            # still works (a node's own IP is inherently a member of its own SG),
            # but the real pod port is equally invisible here, so it's substituted too.
            return Rule(SecurityGroupModulePNS.SGn(m), SecurityGroupModulePNS._vxlan_traffic(traffic))

        return Rule(SecurityGroupModulePNS.SGn(m), traffic)

    @staticmethod
    def _vxlan_traffic(original: Traffic) -> Traffic:
        return Traffic(direction=original.direction, port=network_mode.vxlan_port, protocol="udp")
        

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

        print(f"Removing SG: {SecurityGroupModulePLS.SGn(L)}")

        if SecurityGroupModulePLS.SGn(L) in ClusterState.get_security_groups().keys():
            for n in filter(lambda n: running(L, n), ClusterState.get_nodes()):
                sg = ClusterState.get_security_group(SecurityGroupModulePLS.SGn(L))
                SecurityGroupModulePLS.detach_security_group(sg, n)

            print(f"SGMod: Removing Security Group: {SecurityGroupModulePLS.SGn(L)}")
            try:
                SecurityGroupModulePLS.delete_security_group(SecurityGroupModulePLS.SGn(L))
                ClusterState.remove_security_group(SecurityGroupModulePLS.SGn(L))
            except Exception as e:
                raise Exception(f"Could not remove security group {SecurityGroupModulePLS.SGn(L)} \n {e}")
                
    @staticmethod
    def attach_security_group_to_node(sg: SecurityGroup, node: Node):
        """
        A method used for attaching a security group to an openstack node.
        """
        nova = OpenStackClient().get_nova()
        server = nova.servers.find(name=node.name)
        attached_sgs = {sg["name"] for sg in server.security_groups}

        if sg.name in attached_sgs:
            print(f"{sg.name} already attached to {node.name}")
            return

        security_group_name = sg.name
        sg_id = sg.id
        print(f"Attaching security group {security_group_name} to instance {node.name}")
        try:
            server.add_security_group(sg_id)
            sg.attach_to_node(node)
        
        except Exception as e:
            raise Exception(f"There was a problem attaching SG: {sg.name} to node: {node}\n {e}")

    @staticmethod
    def detach_security_group(sg: SecurityGroup, node: Node):
        """
        A method used for detaching a security group from an openstack node.
        """
        nova = OpenStackClient().get_nova()
        server = nova.servers.find(name=node.name)
        security_group_name = sg.name
        sg_id = sg.id

        print(f"[{threading.get_ident()}] Detaching security group {security_group_name} (id: {sg_id}) from instance {node.name}")
        # print(f" Acquired locks: {SecurityGroupModule.lockmanager._locks}")
        try:
            server.remove_security_group(sg_id)
            sg.detach_from_node(node)
            print(f"Security group '{sg.name}' detached successfully from node: {node.name}")

        except Exception as e:
            raise Exception(f"There was a problem detaching SG: {sg.name} from node: {node}\n {e} \n \
                             This is the internal state of the SG: attached_nodes = {sg.get_attached_nodes_string()}")
    
    @staticmethod
    def delete_security_group(sg_name):
        """Deletes a security group by name."""

        sg_model = ClusterState.get_security_group(sg_name)
        
        if not sg_model:
            raise Exception(f"SG {sg_name} does not exist in ClusterState!")

        # Get security group ID by name
        neutron = OpenStackClient().get_neutron()
        security_groups = neutron.list_security_groups().get("security_groups", [])
        sg = next((sg for sg in security_groups if sg["name"] == sg_name), None)

        if not sg:
            print(f"Security group '{sg_name}' not found.")
            return

        sg_id = sg["id"]
        
        try:
            print(f"[{threading.get_ident()}] Deleting security group: {sg_name} ({sg_id})")
            neutron.delete_security_group(sg_id)
            print(f"[{threading.get_ident()}] Security group '{sg_name}' deleted successfully.")
        except Exception as e:
            raise Exception(f"[{threading.get_ident()}] Failed to delete security group '{sg_name}': {e} \n \
                   This is the internal state of the SG: attached_nodes: {sg_model.get_attached_nodes_string()}")  

    @staticmethod
    def add_rule_to_remotes(sg: SecurityGroup, rule: Rule):
        """
        A method used to add a rule to a given security group.
        """
        try:
            SecurityGroupModule.add_rule_to_remotes(sg, rule)
        except Exception as e:
            print(f"Cannot add rule to remotes: {e}")

    @staticmethod
    def rule_from(spol: Policy):
        """
        A method to create a security group rule from a given splitted policy.

        Returns:

            rule: Rule | The created rule from the splitted policy.
        """
        A, traffic = spol.allow[0]
        return Rule(A if isinstance(A, CIDR) else ClusterState.get_security_group(SecurityGroupModulePLS.SGn(A)), traffic)

