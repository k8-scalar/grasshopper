from classes import CIDR, Node, Policy, Rule, SecurityGroup, LabelSet, Traffic
from cluster_state import ClusterState
from helpers import running, other_policy_provides_traffic
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
        # m is None when pol's peer is a CIDR (ipBlock) - there's no single
        # matched Node for a fixed address block, so rule_from() below uses
        # pol.allow[0][0] (the CIDR itself) as the target instead of m.
        m_desc = m.name if m is not None else pol.allow[0][0]
        if n == m:
            print(f"SGMod: Cannot add connection from {n.name} to itself in PNS mode.")
            return
        # m is None for a CIDR/ipBlock peer - not a cluster node, so segment
        # isolation (defined over cluster node pairs) never applies to it.
        if m is not None and ClusterState.is_isolated(n.name, m.name):
            print(f"SGMod: Blocking connection from {n.name} to {m_desc} - segmentation policy isolates these nodes.")
            return
        print(f"SGMod: Adding connection from {n.name} to {m_desc}")
        rule: Rule = SecurityGroupModulePNS.rule_from(pol, n, m)
        if rule not in SecurityGroupModulePNS.SGn(n).remotes:
            SecurityGroupModule.add_rule_to_remotes(SecurityGroupModulePNS.SGn(n), rule)

    @staticmethod
    def SG_remove_conn(pol: Policy, n: Node, m: Node) -> None:
        m_desc = m.name if m is not None else pol.allow[0][0]
        print(f"SGMod: Removing connection from {n.name} to {m_desc}")
        # Removal is usually triggered by the very pod that made pol match
        # in the first place (already gone from ClusterState by now), so
        # pol's own selector will typically no longer be "running" on n -
        # that's expected, not a reason to skip removal. Only skip if some
        # OTHER policy still needs this exact connection.
        if other_policy_provides_traffic(pol, pol.allow[0][1], n, m):
            print(
                f"SGMod: another policy still requires traffic from node {n.name} to {m_desc}"
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

    @staticmethod
    def revoke_rules_for_isolated_pairs(pairs: set) -> None:
        """
        Tears down any existing dynamic rule between each (n_name, m_name)
        pair in `pairs` - a segmentation change must retroactively revoke
        already-granted connectivity, not just gate future SG_add_conn calls
        (see the ClusterState.is_isolated() check there). Checks BOTH
        directions per pair (n's SG for a rule targeting m, and m's SG for a
        rule targeting n), since which side actually holds the rule depends
        on the NetworkPolicy's ingress/egress direction, not on which node in
        the pair we happen to be looking at. Handles both same-project
        (SecurityGroup target) and cross-project (CIDR-of-peer-node-IP
        target) rule shapes, matching rule_from()'s own two shapes.
        """
        for n_name, m_name in pairs:
            for a_name, b_name in ((n_name, m_name), (m_name, n_name)):
                a_sg = ClusterState.get_security_group("SG_" + a_name)
                if a_sg is None:
                    continue
                b_sg_name = "SG_" + b_name
                b_node = ClusterState.get_node(b_name)
                b_cidr = f"{b_node.internal_ip}/32" if b_node and b_node.internal_ip else None
                for rule in list(a_sg.remotes):
                    target = rule.target
                    matches_b = (
                        (isinstance(target, SecurityGroup) and target.name == b_sg_name)
                        or (isinstance(target, CIDR) and b_cidr is not None and target.cidr == b_cidr)
                    )
                    if matches_b:
                        print(f"SGMod: segmentation isolates {a_name} from {b_name} - revoking existing rule on {a_sg.name}")
                        SecurityGroupModule.remove_rule_from_remotes(a_sg, rule)

    @staticmethod
    def revoke_isolated_connections(node_names=None) -> None:
        """
        Sweeps currently-tracked SG rules and revokes any whose target node
        is presently isolated from the SG's own node - closes a gap
        revoke_rules_for_isolated_pairs() leaves: that one only fires on a
        segmentation CHANGE, diffed against ClusterState's own last-known
        node_segments, so a connection wrongly established while that state
        was still stale for the node(s) involved (a new pod or
        NetworkPolicy processed - SG_add_conn's is_isolated() check
        included - before Grasshopper's own NodeSegmentationPolicy watch had
        caught up) never gets revisited once the state does catch up, since
        nothing about it looks like a "transition" by then. Confirmed live:
        a fresh NetworkPolicy's connection was created spanning two
        already-isolated segments, racing ahead of ClusterState.
        node_segments syncing for the newly (re)scheduled pods' nodes.

        node_names=None (used by the reconciliation loop, every tick)
        sweeps every tracked SG. A given set of node names (used right
        after establishing a new pod's or a new policy's connections)
        scopes it to just those nodes' own SGs - either way this is
        bounded by the number of currently-tracked rules, not by node
        count, so a whole-cluster sweep every reconcile tick stays cheap
        regardless of cluster size.

        A CIDR-typed remote is resolved back to a Node via its address -
        one that doesn't exactly match any currently-known node's IP (a
        genuine ipBlock policy peer, e.g. 172.22.0.0/16, rather than a
        cross-project node-to-node /32) is left alone; it isn't a
        node-to-node connection is_isolated() has any opinion about.
        """
        if node_names is not None:
            sgs = []
            for node_name in node_names:
                sg = ClusterState.get_security_group("SG_" + node_name)
                if sg is not None:
                    sgs.append(sg)
        else:
            sgs = list(ClusterState.get_security_groups().values())

        ip_to_node_name = {
            node.internal_ip: node.name for node in ClusterState.get_nodes() if node.internal_ip
        }

        for sg in sgs:
            if not sg.name.startswith("SG_"):
                continue
            a_name = sg.name[len("SG_"):]
            for rule in list(sg.remotes):
                target = rule.target
                if isinstance(target, SecurityGroup):
                    if not target.name.startswith("SG_"):
                        continue
                    b_name = target.name[len("SG_"):]
                elif isinstance(target, CIDR):
                    b_name = ip_to_node_name.get(target.cidr.split("/")[0])
                    if b_name is None:
                        continue
                else:
                    continue
                if ClusterState.is_isolated(a_name, b_name):
                    print(f"SGMod: segmentation isolates {a_name} from {b_name} - revoking existing rule on {sg.name}")
                    SecurityGroupModule.remove_rule_from_remotes(sg, rule)


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

