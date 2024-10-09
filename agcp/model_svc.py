"""
Kubernetes configuration files models
"""
from typing import *
from dataclasses import dataclass, field
from bitarray import bitarray
from abc import abstractmethod
from credentials import neutron, nova
import ast
from rulz import already_created_rules
from config import singleSGPerNodeScenario

@dataclass
class Container:
    name: str
    labels: Dict[str, str]
    nodeName: str
    select_policies: List[int] = field(default_factory=list)
    allow_policies: List[int] = field(default_factory=list)
    select_services: List[int] = field(default_factory=list)
    

    def getValueOrDefault(self, key: str, value: str):
        if key in self.labels:
            return self.labels[key]
        return value

    def getLabels(self):
        return self.labels

@dataclass
class PolicySelect:
    labels: Dict[str, str]
    is_allow_all = False
    is_deny_all = False

@dataclass
class PolicyAllow:
    labels: Dict[str,str]
    is_allow_all = False
    is_deny_all = False


@dataclass
class PolicyDirection:
    direction: bool

    def is_ingress(self) -> bool:
        return self.direction

    def is_egress(self) -> bool:
        return not self.direction

PolicyIngress = PolicyDirection(True)
PolicyEgress = PolicyDirection(False)

@dataclass
class PolTraffic:
    labels: Dict[str,str]
    traffic: str
    proto: str =None
    port: Any=None
    cidr: Any=None
    allowedPodsNodes: List[str] = None 

@dataclass
class Pol:
    name: str
    select_labels: Dict[str,str]

@dataclass 
class SGRule:
    SGName: str
    traffic: str
    proto: str =None
    port: Any=None
    cidr: Any=None
    remoteSG: str=None

@dataclass
class PolicyProtocol:
    protocols: List[str]

@dataclass
class Mapping:
    SG_name: str
    NetworkPolicy_name: str
    select_labels: Dict[str, str]
    allow_section: Dict[str, str]
    remoteSGs: Any
    target_Node: Any
    target_SGPerNode_Names: List[str] 
    remoteSG_role:bool

@dataclass
class svcMapping:
    serviceName: str
    selectorLabels: Dict[str, str]
    specPorts: Any
    targetNodes: Any

T = TypeVar('T')
class LabelRelation(Protocol[T]):
    @abstractmethod
    def match(self, rule: T, value: T) -> bool:
        raise NotImplementedError


class DefaultEqualityLabelRelation(LabelRelation):
    def match(self, rule: Any, value: Any) -> bool:
        return rule == value

##adding support for service
@dataclass 
class ServiceSelect:
    labels: Dict[str, str]
    is_allow_all = False
    is_deny_all = False

@dataclass
class Svcprotocol:
    port: Any
    protocol: str
    targetPort: Any = None

@dataclass
class ServicePorts:
    protocol: Svcprotocol
    nodePort: Any = None

@dataclass
class Service:
    name: str
    selector: ServiceSelect
    ports: ServicePorts
    ServiceType: str
    service_select_set: bitarray = None
    matcher: LabelRelation[str] = DefaultEqualityLabelRelation()
    service_select_set: bitarray = None

    @property
    def service_selector(self):
        return self.selector

    def select_service(self, container: Container) -> bool:
        cl = container.labels
        sl = self.service_selector.labels
        for k, v in cl.items():
            if k in sl.keys() and \
                not self.matcher.match(sl[k], v):
                return False
        return True

    def store_svc_bcp(self, select_set: bitarray):
        self.service_select_set = select_set


class ServiceReachability:
    def exception_handler(func):
        def inner_function(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(type(e).__name__ + ": " + str(e))
        return inner_function
    

    @staticmethod
    def build_svc(containers: List[Container], services: List[Service]):
        n_container = len(containers)
        n_services = len(services)
        labelMap: Dict[str, bitarray] = DefaultDict(lambda: bitarray('0' * n_container))
        all_map =[] #list of mappings
        index_map = [] # Just to know which index to which pod
        svc_index =[]
        for i, service in enumerate(services):
            svc_index.append('{}:{}'.format(i,service.name))
        for idx, cont_info in enumerate (containers):
            index_map.append('{}:{}'.format(idx,cont_info.name))
        for i, container in enumerate(containers):
            for key, _ in container.labels.items():
                labelMap[key][i] = True               
        for i, service in enumerate(services):
            select_set = bitarray(n_container)
            select_set.setall(True)

            # work as all direction being egress
            for k, _ in service.service_selector.labels.items():
                if k in labelMap.keys(): #all keys in containers
                    select_set &= labelMap[k]
                else:
                    if not service.service_selector.labels:
                        continue
                    select_set.setall(False)

            # dealing with not matched values (needs a customized predicate)
            for idx, cont_info in enumerate (containers):
                if select_set[idx] and not service.select_service(containers[idx]):
                    select_set[idx] = False
           
            service.store_svc_bcp(select_set)

            if service.service_selector.is_allow_all:
                select_set.setall(True)
            elif service.service_selector.is_deny_all:
                select_set.setall(False)           

            for idx in range(n_container):
                if select_set[idx]:
                    containers[idx].select_services.append(i)

            ##for creation of SG
            svc_selected_containers=[]
            for idx in range(n_container):
                if select_set[idx]:
                    svc_selected_containers.append(containers[idx].name)

            SVC_name=service.name          
            sel_node=[]
            SG_node=[]#nodes onto which pods are running. Not important here since nodeport opens the port on all nodes

            for cont in range(len(containers)):
                for item in svc_selected_containers:
                    if containers[cont].name==item:
                        sel_node.append(containers[cont])
            for item in sel_node:
                if item.nodeName not in SG_node:
                    SG_node.append(item.nodeName)
            for _,  items in enumerate(all_map):
                if items.serviceName != SVC_name and \
                    items.selectorLabels ==service.selector.labels: 
                    if items.specPorts.nodePort !=None:
                        print('Service with similar labels already added')
                    else:
                        if service.ports.nodePort !=None:
                            new_map = svcMapping(SVC_name, service.selector.labels, service.ports, SG_node )
                            if new_map not in all_map:
                                all_map.append(new_map)
            else:
                new_map = svcMapping(SVC_name, service.selector.labels, service.ports, SG_node )
                if new_map not in all_map:
                    all_map.append(new_map)     
        return ServiceReachability(n_container, n_services, svc_index, all_map)

    def __init__(self, container_size: int, service_size: int, svc_index, all_map) -> None:
        self.container_size = container_size
        self.service_size = service_size
        self.svc_index = svc_index
        self.all_map = all_map

    @exception_handler 
    def svc_add_rules(svc_maps):
        added_nodeports=[]
        for svc_map in svc_maps:             
            if svc_map.specPorts.nodePort !=None and \
                svc_map.specPorts.nodePort not in added_nodeports:
                if svc_map.targetNodes:
                    added_nodeports.append(svc_map.specPorts.nodePort)
                    sgs = neutron.list_security_groups()['security_groups'] # Reload SG list after addition of new SG
                    s2 =''
                    for sg in sgs:
                        if sg['name']=='workerSG':
                            s2 = sg
                            break
                    if s2!='':
                        IngressRule=SGRule(s2['name'], 'ingress', 'tcp', svc_map.specPorts.nodePort, None, s2['name'])
                        EgressRule=SGRule(s2['name'], 'egress', 'tcp', svc_map.specPorts.nodePort, None, s2['name'])
                        if IngressRule not in already_created_rules:
                            already_created_rules.append(IngressRule)
                            neutron.create_security_group_rule(body={"security_group_rule": {
                                            "direction": 'ingress',
                                            "ethertype": "IPv4",
                                            "protocol": "tcp", # or item.protocol for item in svc_map.allow_section.protocol
                                            "port_range_min": svc_map.specPorts.nodePort,
                                            "port_range_max": svc_map.specPorts.nodePort,
                                            "remote_group_id":s2['id'],
                                            "security_group_id":s2['id'] }
                                        })
                        if EgressRule not in already_created_rules:
                            already_created_rules.append(EgressRule)
                            neutron.create_security_group_rule(body={"security_group_rule": {
                                            "direction": 'egress',
                                            "ethertype": "IPv4",
                                            "protocol": "tcp", # or item.protocol for item in svc_map.allow_section.protocol
                                            "port_range_min": svc_map.specPorts.nodePort,
                                            "port_range_max": svc_map.specPorts.nodePort,
                                            "remote_group_id":s2['id'],
                                            "security_group_id":s2['id'] }
                                        })
            else:
                print('service not of type nodePort')
    @exception_handler               
    def rmv_rules_from_SG(svc_maps, NodePort):
        for svc_map in svc_maps:
            if svc_map.specPorts.nodePort ==NodePort:
                sgs = neutron.list_security_groups()['security_groups'] # Reload SG list after addition of new SG
                s2 =''
                for sg in sgs:
                    if sg['name']=='workerSG':
                        s2 = sg
                        break

                if s2!='':
                    for r in s2['security_group_rules']:
                        if r['port_range_min'] == NodePort and \
                            r['port_range_max'] == NodePort and \
                                r['protocol'] == 'tcp' and \
                                    r['security_group_id'] == s2['id']:
                            neutron.delete_security_group_rule(security_group_rule=r['id'])

    @exception_handler               
    def rmv_rules_from_created_list(sgname, nodeport):
        for rul in already_created_rules:
            if rul.SGName == sgname and \
                rul.traffic == 'ingress' and \
                rul.proto == 'tcp' and\
                rul.port == nodeport:
                    already_created_rules.remove(rul)
        for rul in already_created_rules: # would combine this with previous but remove() removes only the first occurence
            if rul.SGName == sgname and \
                rul.traffic == 'egress' and \
                rul.proto == 'tcp' and\
                rul.port == nodeport:
                    already_created_rules.remove(rul)


@dataclass
class Policy:
    name: str
    selector: PolicySelect
    allow: PolicyAllow
    direction: PolicyDirection
    protocol: PolicyProtocol
    cidr: Any
    matcher: LabelRelation[str] = DefaultEqualityLabelRelation()
    working_select_set: bitarray = None
    working_allow_set: bitarray = None


    @property
    def working_selector(self):
        if self.is_egress():
            return self.selector
        return self.selector

    @property
    def working_allow(self):
        if self.is_egress():
            return self.allow
        return self.allow

    def select_policy(self, container: Container) -> bool:
        cl = container.labels
        sl = self.working_selector.labels
        for k, v in cl.items():
            if k in sl.keys() and \
                not self.matcher.match(sl[k], v):
                return False
        return True

    def allow_policy(self, container: Container) -> bool:
        cl = container.labels
        for items in self.working_allow:
            al = items.labels
        for k, v in cl.items():
            if k in al.keys() and \
                not self.matcher.match(al[k], v):
                return False
        return True

    def is_ingress(self):
        return self.direction.is_ingress()

    def is_egress(self):
        return self.direction.is_egress()

    def store_bcp(self, select_set: bitarray, allow_set: bitarray):
        self.working_select_set = select_set
        self.working_allow_set = allow_set


class NP_object:
    @staticmethod
    def build_sgs(containers: List[Container], policies: List[Policy], InterNode =True):
        n_container = len(containers)
        labelMap: Dict[str, bitarray] = DefaultDict(lambda: bitarray('0' * n_container))
        all_map =[] #list of mappings

        for i, container in enumerate(containers):
            for key, _ in container.labels.items():
                labelMap[key][i] = True

        for i, policy in enumerate(policies):
            select_set = bitarray(n_container)
            select_set.setall(True)
            allow_set = bitarray(n_container)
            allow_set.setall(True)

            # work as all direction being egress
            for k, v in policy.working_selector.labels.items():
                if k in labelMap.keys(): #all keys in containers
                    select_set &= labelMap[k]
                    #If policy labels not on any container, then it does not select any container.
                else:
                    if not policy.working_selector.labels:
                        continue
                    select_set.setall(False)
                    # To add deny all policy, add another condition for policy labels == empty to select all

            for items in  policy.working_allow:
                for k, _ in items.labels.items():
                    if k in labelMap.keys():
                        allow_set &= labelMap[k]

            # dealing with not matched values (needs a customized predicate)
            for idx, _ in enumerate (containers):#in range(n_container):
                if select_set[idx] and not policy.select_policy(containers[idx]):
                    select_set[idx] = False

                if allow_set[idx] and not policy.allow_policy(containers[idx]):
                    allow_set[idx] = False
            policy.store_bcp(select_set, allow_set)

            for items in policy.working_allow:
                if items.is_allow_all:
                    allow_set.setall(True)
                elif items.is_deny_all:
                    allow_set.setall(False)

            if policy.working_selector.is_allow_all:
                select_set.setall(True)
            elif policy.working_selector.is_deny_all:
                select_set.setall(False)

            for idx in range(n_container):
                if allow_set[idx]:
                    containers[idx].allow_policies.append(i)

            for idx in range(n_container):
                if select_set[idx]:
                    #if policies.name not in containers[idx].select_policies:
                        #containers[idx].select_policies.append(policy.name)
                    if i not in containers[idx].select_policies:
                        containers[idx].select_policies.append(i)

            ##for creation of SG
            selected_containers=[]
            for idx in range(n_container):
                if select_set[idx]:
                    selected_containers.append(containers[idx].name)

            allowed_containers=[]
            for idx in range(n_container):
                if allow_set[idx]:
                    allowed_containers.append(containers[idx].name)

            if policy.is_ingress():
                traf_type='ingress'
            if policy.is_egress():
                traf_type='egress'

            NP_name = policy.name
            sg_name = f'SG_{NP_name}'
            allow_sec, SG_from_AllowLabels, SG_role = [], [], False        

            #finding inter-node communications and nodes of selected and allowed containers
            sel_node = [cont for cont in containers if cont.name in selected_containers]
            all_node = [cont for cont in containers if cont.name in allowed_containers]
            all_nodes = list(set(cont.nodeName for cont in all_node))
            interNode_pods = [(item.name, item1.name) for item in sel_node for item1 in all_node if item.nodeName != item1.nodeName]
            SG_node = list(set(item.nodeName for item in sel_node))
            sg_pernode_names = [f'SG_{cont.nodeName}' for cont in sel_node]          
            
            ##mapping SGs to the labels of the policy
            if InterNode and interNode_pods:
                allow_sec.append({'labels': items.labels, 'traffic': traf_type} for items in policy.allow)
                for items in all_map:
                    if items.NetworkPolicy_name == NP_name:
                        items.allow_section.append(iter for iter in allow_sec if iter not in items.allow_section or not items.allow_section)
                        break

                else:
                    all_map.append(Mapping(sg_name, NP_name, policy.selector.labels, allow_sec, SG_from_AllowLabels, SG_node, sg_pernode_names, SG_role))

            if not InterNode:
                SG_node += [cont.nodeName for cont in sel_node if cont.nodeName not in SG_node]

                for items in policy.allow:
                    if not policy.protocol:
                        policy.protocol= ['TCP',1,65535]
                        allow_sec.append(PolTraffic(items.labels, traf_type, policy.protocol[0], [policy.protocol[1],policy.protocol[2]], policy.cidr, all_nodes))
                    elif policy.protocol and type(policy.protocol[0]) is list:
                        for prots in policy.protocol:
                            allow_sec.append(PolTraffic(items.labels, traf_type, prots[0], [prots[1],prots[2]], policy.cidr, all_nodes))
                    else:
                        allow_sec.append(PolTraffic(items.labels, traf_type, policy.protocol[0], [policy.protocol[1],policy.protocol[2]], policy.cidr, all_nodes))

                    #else:
                        #print(policy.protocol)
                        #for prots in policy.protocol:
                        #allow_sec.append(PolTraffic(items.labels, traf_type, prots[0], [prots[1],prots[2]], policy.cidr, all_nodes))
                        #allow_sec.append(PolTraffic(items.labels, traf_type, policy.protocol[0], [policy.protocol[1],policy.protocol[2]], policy.cidr, all_nodes))
                for items in all_map:
                    if items.NetworkPolicy_name == NP_name or items.select_labels == policy.selector.labels:
                        items.NetworkPolicy_name = policy.name
                        items.allow_section.extend(iter for iter in allow_sec if iter not in items.allow_section or not items.allow_section)
                        break
                else:
                    if SG_node:
                        all_map.append(Mapping(sg_name, NP_name, policy.selector.labels, allow_sec, SG_from_AllowLabels, SG_node, sg_pernode_names, SG_role))
        return all_map


    #Create a new mapping list dropping previously stored Nones items if a policy matching then has been added.
    def buildconnections(all_map):
        new_all_map =[]# New mapping
        remSGLabels=[]
        for ite in all_map:
            availSGs=[]#store already created SGs to be added to SG with multiple NPs
            for ite1 in all_map:
                if ite1 != ite:
                    for lab in ite.allow_section:
                        if lab.labels ==ite1.select_labels:
                            if lab.labels not in remSGLabels:
                                remSGLabels.append(lab.labels.items())
                            if ite1.SG_name not in availSGs:
                                availSGs.append (ite1.SG_name)
                            ite.remoteSGs = availSGs
                            ite.remoteSG_role = True
            new_all_map.append(ite)

        for ite in all_map:
            for lala in ite.allow_section:
                if lala.labels.items() not in remSGLabels:
                    ite.remoteSGs=None

        #Adding key labels from the allow section of the policy in the map
        for ite in all_map:
            for vals in ite.allow_section:
                if vals.labels.items() not in remSGLabels:
                    all_sgname='_'.join(['{}_{}'.format(k,v) for k,v in vals.labels.items()])
                    new_map_all = Mapping(all_sgname, None, vals.labels, [], None, None, None, None)
                    if new_map_all not in all_map:
                        all_map.append(new_map_all)
                        remSGLabels.append(vals.labels.items())
                        new_all_map.append(new_map_all)
                else:
                    for ite in new_all_map:
                        if ite.select_labels == vals.labels and ite.NetworkPolicy_name ==None:
                            #print ("{} not added to Map coz similar labels already exist for SG '{}'".format(vals.labels,ite.SG_name))
                            continue
        return new_all_map
    


    def is_subset(dict1, dict2):
        return all(dict1.get(key) == value for key, value in dict2.items())
    
    def concate(new_all_map):
        f_map_list = {}
        from Hmap import h_map 
        
        for v in new_all_map:
            if v.NetworkPolicy_name ==None: # comment out to create template for allow labels of the policy in the map
                continue
            sorted_sel_labels = dict(OrderedDict(sorted(v.select_labels.items(), key=lambda kv: kv[0].casefold())))
            selpolz=[]
            allpolz=[]
                    
            for w in new_all_map:
                if w.NetworkPolicy_name==None:
                    continue 
                if w.select_labels.items() <= v.select_labels.items():
                    if Pol(w.NetworkPolicy_name, w.select_labels) not in selpolz:
                        selpolz.append(Pol(w.NetworkPolicy_name, w.select_labels))
            for z in new_all_map: 
                if z.NetworkPolicy_name == None:
                    continue
                for allowz in z.allow_section:
                    if allowz.labels.items() <= v.select_labels.items():
                        if Pol(z.NetworkPolicy_name, z.select_labels) not in allpolz:
                            allpolz.append(Pol(z.NetworkPolicy_name, z.select_labels)) 
            if not singleSGPerNodeScenario:
                # Check if sorted_sel_labels is in h_map               
                for u, h_map_entry in h_map.items():
                    h_map_dict_key = ast.literal_eval(u)
                    
                    if h_map_dict_key == sorted_sel_labels:
                        for m in h_map_entry:
                            if m['NetworkPolicy_name'] is None:
                                m.update({
                                    'SG_name': v.SG_name,
                                    'NetworkPolicy_name': v.NetworkPolicy_name,
                                    'allow_section': v.allow_section,
                                    'remoteSGs': v.remoteSGs,
                                    'selected_Nodes': v.target_Node,
                                    'target_SGPerNode_Names': v.target_SGPerNode_Names,
                                    'RemoteSG_role': v.remoteSG_role
                                })
                                break

                #If not in the map, create a new map entry
                key = str(sorted_sel_labels)
                d2 = {
                    #'key': str(sorted_sel_labels),
                    'SG_name': v.SG_name,
                    'NetworkPolicy_name': v.NetworkPolicy_name,
                    'select_labels': sorted_sel_labels,
                    'allow_section': v.allow_section,
                    'remoteSGs': v.remoteSGs,
                    'selected_Nodes': v.target_Node,
                    'target_SGPerNode_Names': v.target_SGPerNode_Names,
                    'RemoteSG_role': v.remoteSG_role
                }
                
                #f_map_list.setdefault(d2['key'], []).append(d2)
                f_map_list.setdefault(key, []).append(d2)
            else:
                # Check if sorted_sel_labels is in h_map
                #Not necessary if allow templates not created in the map
                if h_map and h_map!=None:
                    for u, h_map_entry in h_map.items():
                        h_map_dict_key = ast.literal_eval(u)                  
                        if h_map_dict_key == sorted_sel_labels:
                            #if h_map_entry['NetworkPolicy_name'] is None:
                            if h_map_entry['NetworkPolicy_name'].select_labels.items() == v.select_labels.items():
                                h_map_entry.update({
                                    #'SG_name': v.SG_name,
                                    'NetworkPolicy_name': Pol(v.NetworkPolicy_name, sorted_sel_labels), 
                                    'allow_section': v.allow_section,
                                    'selected_Nodes': v.target_Node,
                                    'RemoteSG_role': v.remoteSG_role,
                                    'target_SGPerNode_Names': v.target_SGPerNode_Names,
                                    'selPols': selpolz,
                                    'allowPols': allpolz                                 
                                })
                                break

                #If not in the map, create a new map entry
                key = str(sorted_sel_labels)
                if v.NetworkPolicy_name !=None:
                    polName = v.NetworkPolicy_name
                d2 = {                   
                    'NetworkPolicy_name': Pol(polName, sorted_sel_labels),
                    'allow_section': v.allow_section,
                    'selected_Nodes': v.target_Node,
                    'RemoteSG_role': v.remoteSG_role,
                    'target_SGPerNode_Names': v.target_SGPerNode_Names,
                    'selPols': selpolz,
                    'allowPols': allpolz
                }
                f_map_list[key] = d2
        return f_map_list

    def __init__(self, container_size: int, new_all_map:Any, f_map_list:Any) -> None:
        self.container_size = container_size
        self.new_all_map= new_all_map
        self.f_map_list= f_map_list

class SG_object:

    def exception_handler(func):
        def inner_function(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(type(e).__name__ + ": " + str(e))
        return inner_function


    @exception_handler 
    def SGs_and_rules(f_map_list, singleSGPerNode=False):
        if not singleSGPerNode:
            for _, map_value in f_map_list.items():
                already_created_sgs = []
                insgs = neutron.list_security_groups()['security_groups']
                for sg_items in insgs:
                    already_created_sgs.append(sg_items['name'])
                
                for dict_lis in map_value:               
                    if dict_lis['NetworkPolicy_name'] == None:
                        continue
                    if dict_lis['SG_name'] not in already_created_sgs:
                        secgroup=neutron.create_security_group(body={'security_group':{'name':dict_lis['SG_name'], 'description':"Security group from {}".format(dict_lis['NetworkPolicy_name'])}})
                        for r in secgroup['security_group']['security_group_rules']:
                            neutron.delete_security_group_rule(security_group_rule=r['id'])
                    sgs = neutron.list_security_groups()['security_groups'] # Reload SG list after addition of new SG
                    s2 = ''
                    for sg in sgs:
                        if sg['name']==dict_lis['SG_name']:
                            s2 = sg
                            break
                    if s2!='':
                        if not dict_lis['RemoteSG_role']:
                            for vals  in dict_lis['allow_section']:
                                cidr_rule= SGRule(s2['name'],vals.traffic, vals.proto, vals.port, vals.cidr)
                                rulproto = vals.proto if vals.proto is not None else "tcp"
                                if vals.cidr !=None and cidr_rule not in already_created_rules:                                
                                    neutron.create_security_group_rule(body={"security_group_rule": {
                                                    "direction": vals.traffic,
                                                    "ethertype": "IPv4",
                                                    "protocol": rulproto,
                                                    "port_range_min": vals.port[0],
                                                    "port_range_max": vals.port[1],
                                                    "remote_ip_prefix":vals.cidr,
                                                    "security_group_id":s2['id']}
                                                })  
                                    already_created_rules.append(cidr_rule)

                                elif vals.cidr ==None and dict_lis['NetworkPolicy_name'] !=None:
                                    #print("No remoteIP and no remoteSG for {}".format(dict_lis['select_labels'])) 
                                    continue
                                                                    
                        else:
                            for r_sgs in dict_lis['remoteSGs']:
                                s3=''
                                for sgt in sgs:
                                    if sgt['name']==r_sgs:
                                        s3 = sgt
                                        break
                                if s3!='':

                                    for valz in dict_lis['allow_section']:
                                        cidrRul = SGRule(s2['name'],valz.traffic, valz.proto, valz.port, valz.cidr)
                                        sgrul=SGRule(s2['name'],valz.traffic, valz.proto, valz.port, valz.cidr, s3['name'])
                                        rulproto = valz.proto if valz.proto is not None else "tcp"
                                        if sgrul not in already_created_rules:
                                            already_created_rules.append(sgrul)                                          
                                            neutron.create_security_group_rule(body={"security_group_rule": {
                                                            "direction": valz.traffic,
                                                            "ethertype": "IPv4",
                                                            "protocol": rulproto,
                                                            "port_range_min": valz.port[0],
                                                            "port_range_max": valz.port[1],
                                                            "remote_group_id":s3['id'],
                                                            "security_group_id":s2['id']}
                                                        })

                                        if cidrRul in already_created_rules  and sgrul not in already_created_rules:
                                            already_created_rules.append(sgrul) 
                                            neutron.create_security_group_rule(body={"security_group_rule": {
                                                            "direction": valz.traffic,
                                                            "ethertype": "IPv4",
                                                            "protocol": rulproto,
                                                            "port_range_min": valz.port[0],
                                                            "port_range_max": valz.port[1],
                                                            "remote_group_id":s3['id'],
                                                            "security_group_id":s2['id']}
                                                        })
                                        if cidrRul not in already_created_rules  and valz.cidr !=None: # without "valz.cidr !=None", remote ip of 0.0.0.0/0 will be added to the security group
                                            already_created_rules.append(cidrRul)
                                            neutron.create_security_group_rule(body={"security_group_rule": {
                                                            "direction": valz.traffic,
                                                            "ethertype": "IPv4",
                                                            "protocol": rulproto,
                                                            "port_range_min": valz.port[0],
                                                            "port_range_max": valz.port[1],
                                                            "remote_ip_prefix":valz.cidr,
                                                            "security_group_id":s2['id']}
                                                        })                                                                                                           
        if singleSGPerNode:
            for _, map_value in f_map_list.items():            
                if map_value['NetworkPolicy_name'].name == None:
                    continue
                sgs = neutron.list_security_groups()['security_groups'] # Reload SG list after addition of new SG
                s2 = ''
                for sg in sgs:
                    '''#With empty templates for allow sets
                    if map_value['target_SGPerNode_Names'] !=None:
                        for sgnames in map_value['target_SGPerNode_Names']:
                            if sg['name']==sgnames:
                                s2 = sg
                                break'''
                    if map_value['target_SGPerNode_Names'] == None:
                        continue
                    for sgnames in map_value['target_SGPerNode_Names']:
                        if sg['name']==sgnames:
                            s2 = sg
                            break
                    if s2!='':
                        if not map_value['RemoteSG_role']:
                            for vals  in map_value['allow_section']:
                                cidr_rule= SGRule(s2['name'],vals.traffic, vals.proto, vals.port, vals.cidr)
                                rulproto = vals.proto if vals.proto is not None else "tcp"
                                if vals.cidr !=None and cidr_rule not in already_created_rules:                                
                                    neutron.create_security_group_rule(body={"security_group_rule": {
                                                    "direction": vals.traffic,
                                                    "ethertype": "IPv4",
                                                    "protocol": rulproto,
                                                    "port_range_min": vals.port[0],
                                                    "port_range_max": vals.port[1],
                                                    "remote_ip_prefix":vals.cidr,
                                                    "security_group_id":s2['id']}
                                                })  
                                    already_created_rules.append(cidr_rule)

                                elif vals.cidr ==None and map_value['NetworkPolicy_name'].name !=None:
                                    #print("No remoteIP and no remoteSG for {}".format(map_value['select_labels']))
                                    continue 
                                                                    
                        else:
                            for rulz in map_value['allow_section']:
                                for r_nodes in rulz.allowedPodsNodes:
                                    r_sgs = 'SG_'+r_nodes
                                    s3=''
                                    for sgt in sgs:
                                        if sgt['name']==r_sgs:
                                            s3 = sgt
                                            break
                                    if s3!='' and s3!=s2: #otherwise a security group will refer to itself as remote

                                        for valz in map_value['allow_section']:
                                            cidrRul = SGRule(s2['name'],valz.traffic, valz.proto, valz.port, valz.cidr)
                                            sgrul=SGRule(s2['name'],valz.traffic, valz.proto, valz.port, valz.cidr, s3['name'])
                                            rulproto = valz.proto if valz.proto is not None else "tcp"
                                            if sgrul not in already_created_rules:
                                                already_created_rules.append(sgrul)                                          
                                                neutron.create_security_group_rule(body={"security_group_rule": {
                                                                "direction": valz.traffic,
                                                                "ethertype": "IPv4",
                                                                "protocol": rulproto,
                                                                "port_range_min": valz.port[0],
                                                                "port_range_max": valz.port[1],
                                                                "remote_group_id":s3['id'],
                                                                "security_group_id":s2['id']}
                                                            })

                                            if cidrRul in already_created_rules  and sgrul not in already_created_rules:
                                                already_created_rules.append(sgrul) 
                                                neutron.create_security_group_rule(body={"security_group_rule": {
                                                                "direction": valz.traffic,
                                                                "ethertype": "IPv4",
                                                                "protocol": rulproto,
                                                                "port_range_min": valz.port[0],
                                                                "port_range_max": valz.port[1],
                                                                "remote_group_id":s3['id'],
                                                                "security_group_id":s2['id']}
                                                            })
                                            if cidrRul not in already_created_rules  and valz.cidr !=None: # without "valz.cidr !=None", remote ip of 0.0.0.0/0 will be added to the security group
                                                already_created_rules.append(cidrRul)
                                                neutron.create_security_group_rule(body={"security_group_rule": {
                                                                "direction": valz.traffic,
                                                                "ethertype": "IPv4",
                                                                "protocol": rulproto,
                                                                "port_range_min": valz.port[0],
                                                                "port_range_max": valz.port[1],
                                                                "remote_ip_prefix":valz.cidr,
                                                                "security_group_id":s2['id']}
                                                            })                                                                                                          


    @exception_handler
    def attach_an_sg(f_map_list,labels):
        for map_key, map_value in f_map_list.items():
            if ast.literal_eval(map_key).items() >= ast.literal_eval(labels).items():
                for dict_lis in map_value:
                    if ast.literal_eval(labels).items() < dict_lis['select_labels'].items():#If not all select match container, don't attach
                        continue
                    if dict_lis['selected_Nodes']!=None:
                        for nd_nms in dict_lis['selected_Nodes']:
                            instance = nova.servers.find(name=nd_nms)
                            instance.add_security_group(dict_lis['SG_name'])


    @exception_handler
    def attach_an_sgv2(f_map_list, labels, t_node):
        for map_key, map_value in f_map_list.items():
            if ast.literal_eval(map_key).items() <= ast.literal_eval(labels).items(): 
                for dict_lis in map_value:
                    if dict_lis['selected_Nodes'] != None:
                        if ast.literal_eval(labels).items() < dict_lis['select_labels'].items(): 
                            continue
                        instance = nova.servers.find(name=t_node)
                        #instance.add_security_group(dict_lis['SG_name'])
                        try:
                            instance.add_security_group(dict_lis['SG_name'])
                        except Exception as e:
                            if "Duplicate items" in str(e):
                                print(f"security group {dict_lis['SG_name']} already attached")
                            else:
                                print("Error: {}".format(e))
                    else:
                        print("No policy selecting labels {}".format(dict_lis['select_labels']))

    @exception_handler
    def detach_an_sg(tgt_node, sgname):
        instance = nova.servers.find(name=tgt_node)
        instance.remove_security_group(sgname)

    @exception_handler
    def detach_an_sgvs_pod(fg_map, labels, tgt_node,rmv_rules):
        for ke, valz in fg_map.items():
             if ast.literal_eval(labels).items() >= ast.literal_eval(ke).items():
                  for va in valz:
                       instance = nova.servers.find(name=tgt_node)
                       #instance.remove_security_group(va['SG_name'])
                       instance.remove_security_group(va['SG_name']) if va['SG_name'] in [sg['name'] for sg in instance.security_groups] else None
                       print("Security group {} detached from node {}".format(va['SG_name'], tgt_node))
                       if rmv_rules:
                           security_group = next((sg for sg in neutron.list_security_groups()['security_groups'] if sg['name'] == va['SG_name']), None)
                           for r in security_group['security_group_rules']:
                               neutron.delete_security_group_rule(security_group_rule=r['id'])
    
    @exception_handler
    def detach_an_sgvs_policy(fg_map, labels, delete_sg):
        for ke, valz in fg_map.items():
                if ast.literal_eval(labels).items() <= ast.literal_eval(ke).items():
                    for va in valz:
                        for sg in neutron.list_security_groups()['security_groups']:
                            if sg['name']==va['SG_name']:
                                sgName=sg
                        if va['selected_Nodes'] !=None:
                            for nodes in va['selected_Nodes']:
                                instance = nova.servers.find(name=nodes)
                                #instance.remove_security_group(sgName['name'])
                                instance.remove_security_group(sgName['name']) if sgName['name'] in [sg['name'] for sg in instance.security_groups] else None
                                if sgName not in instance.security_groups:
                                    print("Security group {} detached from node {}".format(sgName['name'], nodes))
                        if delete_sg:
                            remoteSG=None
                            #First remove the remote rules that refer to this SG 
                            for SGs in va['remoteSGs']:
                                for rulz in va['allow_section']:                                       
                                    traffic=rulz.traffic
                                    protocol=rulz.proto
                                    ports=rulz.port
                                    port_min, port_max = (None, None) if ports == [1, 65535] else (ports[0], ports[1])
                                    cidr=rulz.cidr
                                    for sg in neutron.list_security_groups()['security_groups']:
                                        if sg['name']==SGs:
                                            remoteSG=sg                                                     
                                            for r in remoteSG['security_group_rules']:
                                                if r['remote_group_id'] == sgName['id']:
                                                    neutron.delete_security_group_rule(security_group_rule=r['id']) 
                                    for rul in already_created_rules:                                              
                                        if rul.SGName ==sgName['name'] and \
                                            rul.traffic == traffic and \
                                            rul.proto == protocol and \
                                            rul.port[0] == ports[0] and \
                                            rul.port[1] == ports[1] and \
                                            rul.cidr == cidr and \
                                            rul.remoteSG == SGs:
                                                already_created_rules.remove(rul)
                                        if rul.SGName ==SGs and \
                                            rul.remoteSG == sgName['name']:
                                                already_created_rules.remove(rul)
                            neutron.delete_security_group(sgName['id'])  
                            print("Security group {} deleted from the cluster".format(sgName['name']))

                        else:
                            for SGs in va['remoteSGs']:
                                for rulz in va['allow_section']:                                       
                                    traffic=rulz.traffic
                                    protocol=rulz.proto
                                    ports=rulz.port
                                    port_min, port_max = (None, None) if ports == [1, 65535] else (ports[0], ports[1])
                                    cidr=rulz.cidr
                                    for sg in neutron.list_security_groups()['security_groups']:
                                        if sg['name']==SGs:
                                            remoteSG=sg            
                                            for r in sgName['security_group_rules']:
                                                if r['direction'] == traffic and \
                                                    r['protocol'] == protocol.lower() and \
                                                        r['port_range_min']==port_min and \
                                                            r['port_range_max']==port_max and \
                                                                r['remote_ip_prefix'] == cidr and \
                                                                    r['security_group_id'] == sgName['id'] and\
                                                                        r['remote_group_id'] == remoteSG['id']:
                                                    neutron.delete_security_group_rule(security_group_rule=r['id']) 
                                            #Also remove the remote rules that refer to this SG
                                            for r in remoteSG['security_group_rules']:
                                                if r['remote_group_id'] == sgName['id']:
                                                    neutron.delete_security_group_rule(security_group_rule=r['id']) 

                                            for rul in already_created_rules:                                              
                                                if rul.SGName ==sgName['name'] and \
                                                    rul.traffic == traffic and \
                                                    rul.proto == protocol and \
                                                    rul.port[0] == ports[0] and \
                                                    rul.port[1] == ports[1] and \
                                                    rul.cidr == cidr and \
                                                    rul.remoteSG == remoteSG['name']:
                                                        already_created_rules.remove(rul)
                                                if rul.SGName ==remoteSG['name'] and \
                                                    rul.remoteSG == sgName['name']:
                                                        already_created_rules.remove(rul)

    @exception_handler
    def delete_an_sg(sgname):
        for sg in neutron.list_security_groups()['security_groups']:
            if sg['name']==sgname:
                neutron.delete_security_group(sg['id'])
                
# Need to combine the next two functions
    @exception_handler               
    def rmv_rules_from_created_list(sgname):
        for rul in already_created_rules:
            if rul.SGName == sgname:
                already_created_rules.remove(rul) #only removes first occurence 



    @exception_handler  #Seems like this is effective only for cidr.                          
    def rmv_rules(sgName, traffic, protocol, port, cidr):
        for rul in already_created_rules: 
            try:
                while rul.SGName ==sgName and \
                rul.traffic == traffic and \
                rul.proto == protocol and \
                rul.port == port and \
                rul.cidr == cidr:
                    already_created_rules.remove(rul)  
            except ValueError:
                pass               

    @exception_handler                            
    def rmv_rules_rmsg(sgName, traffic, protocol, port, cidr, remoteSG):
        for rul in already_created_rules: 
            try:
                while rul.SGName ==sgName and \
                rul.traffic == traffic and \
                rul.proto == protocol and \
                rul.port == port and \
                rul.cidr == cidr and \
                rul.remoteSG == remoteSG:
                    already_created_rules.remove(rul)  
            except ValueError:
                pass


    @exception_handler
    def rmv_rules_from_pernodeSG_policy(f_map_list, labels):
        sgs = neutron.list_security_groups()['security_groups'] 
        for map_key, map_value in f_map_list.items():
            if ast.literal_eval(map_key).items() == ast.literal_eval(labels).items(): 
                for t_node in map_value['selected_Nodes']:
                    for sg in sgs:
                        if sg['name']=='SG_'+t_node:
                            sgName=sg
                            print("The following rules in " + sgName['name'] + " applied to multiple co-located pods:")
                    for rulz in map_value['allow_section']:
                        for nodez in rulz.allowedPodsNodes:
                            traffic=rulz.traffic
                            protocol=rulz.proto
                            ports=rulz.port
                            port_min, port_max = (None, None) if ports == [1, 65535] else (ports[0], ports[1])
                            cidr=rulz.cidr
                            for sgr in sgs:
                                if sgr['name']=='SG_'+nodez:
                                    remoteSG=sgr             
                                    for r in sgName['security_group_rules']:
                                        if r['direction'] == traffic and \
                                            r['protocol'] == protocol.lower() and \
                                                r['port_range_min']==port_min and \
                                                    r['port_range_max']==port_max and \
                                                        r['remote_ip_prefix'] == cidr and \
                                                            r['security_group_id'] == sgName['id'] and\
                                                                r['remote_group_id'] == remoteSG['id']:
                                            try: 
                                                neutron.delete_security_group_rule(security_group_rule=r['id'])  
                                            except Exception as e:
                                                #Rule already deleted
                                                #print("traffic: " + traffic + " , protocol: " + protocol.lower() + ", port_min: " + port_min if not None else "*" + ", port_max: " + port_max  if not None else "*" + ", remote_cidr: " + cird  if not None else "-" + ", remote_sg: " + remoteSG['name'])
                                                print("traffic: " + traffic + " , protocol: " + protocol.lower() + ", remote_sg: " + remoteSG['name'])

                                    for rul in already_created_rules:                                              
                                        if rul.SGName ==sgName['name'] and \
                                            rul.traffic == traffic and \
                                            rul.proto == protocol and \
                                            rul.port[0] == ports[0] and \
                                            rul.port[1] == ports[1] and \
                                            rul.cidr == cidr and \
                                            rul.remoteSG == remoteSG['name']:
                                                already_created_rules.remove(rul)

    @exception_handler
    def rmv_rules_from_pernodeSG_pod(f_map_list, labels, node, rmv_maprule):
        sgs = neutron.list_security_groups()['security_groups'] 
        for map_key, map_value in f_map_list.items():
            if ast.literal_eval(map_key).items() <= ast.literal_eval(labels).items(): 
                for sg in sgs:
                    if sg['name']=='SG_'+node:
                        sgName=sg
                print("The following rules in " + sgName['name'] + " applied to multiple co-located pods:")
                for rulz in map_value['allow_section']:
                    for nodez in rulz.allowedPodsNodes:
                        traffic=rulz.traffic
                        protocol=rulz.proto
                        ports=rulz.port
                        port_min, port_max = (None, None) if ports == [1, 65535] else (ports[0], ports[1])
                        cidr=rulz.cidr
                        for sgr in sgs:
                            if sgr['name']=='SG_'+nodez:
                                remoteSG=sgr             
                                for r in sgName['security_group_rules']:
                                    if r['direction'] == traffic and \
                                        r['protocol'] == protocol.lower() and \
                                            r['port_range_min']==port_min and \
                                                r['port_range_max']==port_max and \
                                                    r['remote_ip_prefix'] == cidr and \
                                                        r['security_group_id'] == sgName['id'] and\
                                                            r['remote_group_id'] == remoteSG['id']:
                                        try:
                                            neutron.delete_security_group_rule(security_group_rule=r['id']) 
                                        except Exception as e:
                                            print("traffic: " + traffic + " , protocol: " + protocol.lower() + ", remote_sg: " + remoteSG['name'])
                                    if rmv_maprule:
                                        for rul in already_created_rules:                                              
                                            if rul.SGName ==sgName['name'] and \
                                                rul.traffic == traffic and \
                                                rul.proto == protocol and \
                                                rul.port[0] == ports[0] and \
                                                rul.port[1] == ports[1] and \
                                                rul.cidr == cidr and \
                                                rul.remoteSG == remoteSG['name']:
                                                    already_created_rules.remove(rul)


