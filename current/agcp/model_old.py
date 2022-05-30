import sys
if sys.version_info >= (3, 8):
    from typing import *
else:
    from typing_extensions import *
from dataclasses import dataclass, field
from bitarray import bitarray
from abc import abstractmethod
from neutronclient.v2_0 import client as neutclient
from novaclient import client as novaclient
from credentials import get_nova_creds
creds = get_nova_creds()
nova = novaclient.Client(**creds)
neutron = neutclient.Client(**creds)
import ast


@dataclass
class Container:
    name: str
    labels: Dict[str, str]
    nodeName: str
    select_policies: List[int] = field(default_factory=list)
    allow_policies: List[int] = field(default_factory=list)

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
    # true for ingression, false for egress
    direction: bool

    def is_ingress(self) -> bool:
        return self.direction

    def is_egress(self) -> bool:
        return not self.direction


PolicyIngress = PolicyDirection(True)
PolicyEgress = PolicyDirection(False)


@dataclass
class PolicyProtocol:
    protocols: List[str]

@dataclass
class Mapping:
    SG_name: str
    NetworkPolicy_name: str
    select_labels: Dict[str, str]
    allow_section: Dict[str, str]
    AllowLabels_SG_name: Any
    target_Node: Any
    Rem_SG_role:bool



T = TypeVar('T')
class LabelRelation(Protocol[T]):
    @abstractmethod
    def match(self, rule: T, value: T) -> bool:
        raise NotImplementedError


class DefaultEqualityLabelRelation(LabelRelation):
    def match(self, rule: Any, value: Any) -> bool:
        return rule == value


@dataclass
class Policy:
    name: str
    selector: PolicySelect
    allow: PolicyAllow
    direction: PolicyDirection
    protocol: PolicyProtocol
    ##port: PolicyPort
    cidr: Any
    matcher: LabelRelation[str] = DefaultEqualityLabelRelation()
    working_select_set: bitarray = None
    working_allow_set: bitarray = None


    @property
    def working_selector(self):
        if self.is_egress():
            return self.selector
        #return self.allow
        return self.selector

    @property
    def working_allow(self):
        if self.is_egress():
            return self.allow
        #return self.selector
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
            for key, value in container.labels.items():
                labelMap[key][i] = True

        for i, policy in enumerate(policies):
            select_set = bitarray(n_container)
            select_set.setall(True)
            allow_set = bitarray(n_container)
            allow_set.setall(True)

            for k, v in policy.working_selector.labels.items():
                if k in labelMap.keys(): #all keys in containers
                    select_set &= labelMap[k]
                else:
                    if not policy.working_selector.labels:
                        continue
                    select_set.setall(False)
                    # To add deny all policy, add another condition for policy labels == empty to select all

            for items in  policy.working_allow:
                for k, v in items.labels.items():
                    if k in labelMap.keys():
                        allow_set &= labelMap[k]

            for idx, cont_info in enumerate (containers):#in range(n_container):
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
                    containers[idx].select_policies.append(policy.name)

            ##for creation of SG
            selected_containers=[]
            for idx in range(n_container):
                if select_set[idx]:
                    selected_containers.append(containers[idx].name)

            allowed_containers=[]
            for idx in range(n_container):
                if allow_set[idx]:
                    allowed_containers.append(containers[idx].name)

            NP_name=policy.name
            sg_name='SG_{}'.format(policy.name)
            allow_sec =[]
            SG_all_sec=[]
            all_to_sel=[] #Since more than one policies can have same select but different allow, one AllowLabels_SG_name may correspond to one or more SG_names
            SG_role=False
            if policy.cidr:
                CIDR = policy.cidr
            else:
                CIDR = None

            for n in range(len(all_map)):
                for iter in all_map[n].allow_section:
                    if policy.selector.labels.items() == iter['labels'].items():
                        for allSgnames in all_map[n].AllowLabels_SG_name:
                            sg_name = allSgnames

                    for paitems in policy.allow:
                        if paitems.labels.items() == iter['labels'].items(): # if there is already a policy with similar allow labels
                            SG_from_AllowLabels = all_map[n].AllowLabels_SG_name

                        if paitems.labels.items() == all_map[n].select_labels.items() or paitems.labels.items() <= all_map[n].select_labels.items():
                            SG_from_Allow = all_map[n].SG_name
                            if SG_from_Allow not in all_to_sel:
                                all_to_sel.append(SG_from_Allow)


            for hmitems in all_map:
                if hmitems.SG_name in all_to_sel:
                    hmitems.Rem_SG_role = True
                for asitems in hmitems.allow_section:
                    if asitems['labels'] == policy.working_selector.labels:
                        SG_role=True


            #finding inter-node communications and nodes of selected and allowed containers
            sel_node=[]
            all_node=[]
            interNode_pods=[]
            SG_node=[]#These are the nodes onto which to attach the SG from this policy
            for cont in range(len(containers)):
                for item in selected_containers:
                    if containers[cont].name==item:
                        sel_node.append(containers[cont])
                for item1 in allowed_containers:
                    if containers[cont].name==item1:
                        all_node.append(containers[cont])

            for item in sel_node:
                for item1 in all_node:
                    if item.nodeName != item1.nodeName:
                        interNode_pods.append((item.name, item1.name))
                        if item.nodeName not in SG_node:
                            SG_node.append(item.nodeName)


            ##mapping SGs to the labels of the policy
            if InterNode:
                if  interNode_pods:
                    if policy.is_ingress():
                        traf_type='ingress'
                    if policy.is_egress():
                        traf_type='egress'

                    for items in policy.allow:
                        allow_sec.append({'labels':items.labels, 'traffic':traf_type})


                    if len(allow_sec)==1:
                        SG_from_AllowLabels= 'All_{}'.format(sg_name)
                    else:
                        SG_all_sec=[]
                        for idx, items in enumerate(allow_sec):
                            all_sgname='_'.join(['{}_{}'.format(k,v) for k,v in items['labels'].items()])
                            SG_all_sec.append('All_{}_{}'.format(all_sgname,sg_name))
                        SG_from_AllowLabels= SG_all_sec

                    for ind,  items in enumerate(all_map):
                        if items.NetworkPolicy_name == NP_name:# and items.allow_section !=allow_sec:
                            for iter in allow_sec:
                                if iter not in items.allow_section or items.allow_section ==[]:
                                    items.allow_section.append(iter)
                            for sg_all in SG_all_sec:
                                if sg_all not in items.AllowLabels_SG_name:# or items.allow_section ==[]:
                                    items.AllowLabels_SG_name.append(sg_all)
                            break

                    else:
                        new_map = Mapping(sg_name, NP_name, policy.selector.labels, allow_sec, SG_from_AllowLabels, SG_node, SG_role)
                        if new_map not in all_map:
                            all_map.append(new_map)


            if not InterNode:
                for cont in range(len(containers)):
                    for item in selected_containers:
                        if containers[cont].name==item:
                            sel_node.append(containers[cont])

                for item in sel_node:
                    if item.nodeName not in SG_node:
                        SG_node.append(item.nodeName)

                if policy.is_ingress():
                    traf_type='ingress'
                if policy.is_egress():
                    traf_type='egress'

                for items in policy.allow:
                    if policy.cidr:
                        allow_sec.append({'labels':items.labels, 'traffic':traf_type, 'cidr':policy.cidr})
                    else:
                        allow_sec.append({'labels':items.labels, 'traffic':traf_type})
                if len(allow_sec)==1:
                    if not all_to_sel:
                        SG_from_AllowLabels= ['All_{}'.format(sg_name)]
                    else:
                        SG_from_AllowLabels = all_to_sel

                else:
                    if not all_to_sel:
                        SG_all_sec=[]
                        for idx, items in enumerate(allow_sec):
                            all_sgname='_'.join(['{}_{}'.format(k,v) for k,v in items['labels'].items()])
                            SG_all_sec.append('All_{}_{}'.format(all_sgname,sg_name))
                        SG_from_AllowLabels= SG_all_sec
                    else:
                        SG_from_AllowLabels = all_to_sel

                for ind,  items in enumerate(all_map):
                    if items.NetworkPolicy_name == NP_name:# and items.allow_section !=allow_sec:
                        for iter in allow_sec:
                            if iter not in items.allow_section or items.allow_section ==[]:
                                items.allow_section.append(iter)
                        lis_of_all_sgnames =[]
                        for sg_all in SG_all_sec:
                            lis_of_all_sgnames.append(sg_all)
                            if sg_all not in items.AllowLabels_SG_name:# or items.allow_section ==[]:
                                items.AllowLabels_SG_name.append(sg_all)
                        break

                else:
                    new_map = Mapping(sg_name, NP_name, policy.selector.labels, allow_sec, SG_from_AllowLabels, SG_node, SG_role)
                    if new_map not in all_map \
                        and SG_node: # Policy select labels must select atleast one container
                        all_map.append(new_map)

            #Adding key labels from the allow section of the policy in the map
        for obj_map in all_map:
            for valz in obj_map.allow_section:
                policy.selector.labels = valz['labels']
                # If ppolicy allow similar labels in different directions, avoid adding duplicate value to label keys in HashMap
                for itemz in all_map:
                    if itemz.select_labels == policy.selector.labels and itemz.NetworkPolicy_name ==None:
                     #if itemz.SG_name == SG_from_AllowLabels and itemz.select_labels == policy.selector.labels and itemz.NetworkPolicy_name ==None:
                        print ("SG {} not added to Map coz labels {} already exist in map".format(itemz.SG_name, policy.selector.labels))
                        break

                else:
                    if isinstance (obj_map.AllowLabels_SG_name, list): #only a list if more than one values
                        #for more than one item in AllowLabels_SG_name, search for matching key labels
                        str_key_labels = '_'.join(['{}_{}'.format(k,v) for k,v in policy.selector.labels.items()])
                        for sg_all_itemz in obj_map.AllowLabels_SG_name:
                            if str_key_labels in sg_all_itemz:
                                SG_from_AllowLabels = sg_all_itemz
                                new_map_all = Mapping(SG_from_AllowLabels, None, policy.selector.labels, [], None, None, None)
                                all_map.append(new_map_all)
                    else:
                        new_map_all = Mapping(obj_map.AllowLabels_SG_name, None, policy.selector.labels, [], None, None, None)
                        all_map.append(new_map_all)

        #Create a new mapping list dropping previously stored Nones items if a policy matching then has been added.
        new_map = []# Store duplicates in this list
        new_all_map =[]# New mapping
        for ite in all_map:
            for ite1 in all_map:
                if ite != ite1 and ite.select_labels ==ite1.select_labels:
                    new_map.append(ite)
            if ite not in new_map:
                new_all_map.append(ite)
        for itte in new_map:
            if itte not in new_all_map and itte.NetworkPolicy_name !=None :
                new_all_map.append(itte)

        return new_all_map

    #change list of mappings into a dictionary with sorted label strings as keys and the rest as the value
    def concate(new_all_map):
        f_map_list ={} # HashMap with value as a list of dictionaries
        d1 = []
        for v in new_all_map:
            d2 = {}
            allow_sec = []
            all_cidr=[]
            sorted_sel_labels = dict(OrderedDict(sorted(v.select_labels.items(), key = lambda kv:kv[0].casefold())))

            for iter in v.allow_section:
                sorted_all_labels = dict(OrderedDict(sorted(iter['labels'].items(), key = lambda kv:kv[0].casefold())))
                if "cidr" in iter:
                    allow_sec.append({'labels':sorted_all_labels, 'traffic':iter['traffic']})
                    cidr_sec = {'ipBlock':{'CIDR':iter['cidr'], 'traffic':iter['traffic']}}
                    if cidr_sec not in all_cidr:
                        all_cidr.append(cidr_sec)
                else:
                    allow_sec.append({'labels':sorted_all_labels, 'traffic':iter['traffic']})

            if all_cidr:
                for ipblock in all_cidr:
                    allow_sec.append(ipblock)


            d2['key'] = str(sorted_sel_labels)
            d2['SG_name']=v.SG_name
            d2['NetworkPolicy_name']=v.NetworkPolicy_name
            d2['select_labels'] = sorted_sel_labels
            d2['allow_section'] = allow_sec
            d2['AllowLabels_SG_name'] = v.AllowLabels_SG_name
            d2['node_Name']=v.target_Node
            d2['RemoteSG_role']=v.Rem_SG_role
            d1.append(d2)


        f_map ={} # map for dictionaries
        for sg in d1:
            if sg['key'] not in f_map_list: #and not [lis2 for p in lis_key if all(item in p for item in lis2)]:
                f_map[sg['key']]={} #individual  values for each key
                f_map_list[sg['key']] = [] #list of values if a key has more than one value
                for k in sg.keys():
                    if k =='key':
                        continue
                    f_map[sg['key']][k] = sg[k]
                f_map_list[sg['key']].append(f_map[sg['key']])

            else:
                d2 = {}
                d2[sg['key']]={}
                for k in sg.keys():
                    if k =='key':
                        continue
                    d2[sg['key']][k] = sg[k]
                f_map_list[sg['key']].append(d2[sg['key']])
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
    def SGs_and_rules(f_map_list):
        sg_traffic_map =[] # for matching traffic for the rules added to the already previously created SGs
        for map_key, map_value in f_map_list.items():
            already_created_sgs = []
            insgs = neutron.list_security_groups()['security_groups']
            for sg_items in insgs:
                already_created_sgs.append(sg_items['name'])
            for dict_lis in map_value:
                for valz in dict_lis['allow_section']:
                    try:
                        sg_traffic_map.append({'SG_name': dict_lis['SG_name'], 'traffic': valz['traffic']})
                    except KeyError:
                        continue
                #Create new group only if not existing in Openstack.
                if dict_lis['SG_name'] in already_created_sgs:
                    continue

                if dict_lis['NetworkPolicy_name'] == None:
                    continue

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
                        continue

                    else:
                        for r_sgs in dict_lis['AllowLabels_SG_name']:
                            s3=''
                            for sgt in sgs:
                                if sgt['name']==r_sgs:
                                    s3 = sgt
                                    break
                            if s3!='':
                                for iter in dict_lis['allow_section']:
                                    neutron.create_security_group_rule(body={"security_group_rule": {
                                                    "direction": iter['traffic'],
                                                    "ethertype": "IPv4",
                                                    "protocol": "tcp",
                                                    "port_range_min": ,# enter port range here
                                                    "port_range_max": ,
                                                    "remote_group_id":s3['id'],
                                                    "security_group_id":s2['id'] }
                                                })
                                    neutron.create_security_group_rule(body={"security_group_rule": {
                                                    "direction": iter['traffic'],
                                                    "ethertype": "IPv4",
                                                    "protocol": "udp",
                                                    "port_range_min": 4789, #port for vxlan
                                                    "port_range_max": 4789,
                                                    "remote_group_id":s3['id'],
                                                    "security_group_id":s2['id'] }
                                                })
                            if r_sgs in already_created_sgs:
                                sgg=''
                                for items in insgs:
                                    if items['name'] == r_sgs:
                                        sgg = items
                                        break
                                if sgg!='':
                                    for d in sg_traffic_map:
                                        if d['SG_name'] ==r_sgs:
                                            traffic = d['traffic']
                                            neutron.create_security_group_rule(body={"security_group_rule": {
                                                            "direction": traffic,
                                                            "ethertype": "IPv4",
                                                            "protocol": "tcp",
                                                            "port_range_min": , # enter port range here
                                                            "port_range_max": ,
                                                            "remote_group_id":s2['id'],
                                                            "security_group_id":sgg['id'] }
                                                        })
                                            neutron.create_security_group_rule(body={"security_group_rule": {
                                                            "direction": traffic,
                                                            "ethertype": "IPv4",
                                                            "protocol": "udp",
                                                            "port_range_min": 4789, #port for vxlan
                                                            "port_range_max": 4789,
                                                            "remote_group_id":s2['id'],
                                                            "security_group_id":sgg['id'] }
                                                        })


    @exception_handler
    def attach_all_sgs(f_map_list):
        for map_key, map_value in f_map_list.items():
            for dict_lis in map_value:
                instance = nova.servers.find(name=dict_lis['node_Name'])
                instance.add_security_group(dict_lis['SG_name'])


    @exception_handler
    def attach_an_sg(f_map_list,labels):
        for map_key, map_value in f_map_list.items():
            if ast.literal_eval(map_key).items() >= ast.literal_eval(labels).items():
                for dict_lis in map_value:
                    if ast.literal_eval(labels).items() < dict_lis['select_labels'].items():#If not all select match container, don't attach
                        continue
                    for nd_nms in dict_lis['node_Name']:
                        instance = nova.servers.find(name=nd_nms)
                        instance.add_security_group(dict_lis['SG_name'])


    @exception_handler
    def attach_an_sgv2(f_map_list, labels, t_node):
        for map_key, map_value in f_map_list.items():
            if ast.literal_eval(map_key).items() <= ast.literal_eval(labels).items(): #looks like this slightly slower than next line
            #if map_key >= labels:
                for dict_lis in map_value:
                    if ast.literal_eval(labels).items() < dict_lis['select_labels'].items(): #looks slower than next line
                    #if labels > str(dict_lis['select_labels']):
                        continue
                    instance = nova.servers.find(name=t_node)
                    instance.add_security_group(dict_lis['SG_name'])

    @exception_handler
    def detach_all_sgs(f_map_list):
        for map_key, map_value in f_map_list.items():
            for dict_lis in map_value:
                instance = nova.servers.find(name=dict_lis['node_Name'])
                instance.remove_security_group(dict_lis['SG_name'])


    @exception_handler
    def detach_an_sg(tgt_node, sgname):
        instance = nova.servers.find(name=tgt_node)
        instance.remove_security_group(sgname)


    @exception_handler
    def delete_all_sgs(f_map_list):
        for map_key, map_value in f_map_list.items():
            for dict_lis in map_value:
                for sg in neutron.list_security_groups()['security_groups']:
                    if sg['name']==dict_lis['SG_name']:
                        neutron.delete_security_group(sg['id'])

    @exception_handler
    def delete_an_sg(sgname):
        for sg in neutron.list_security_groups()['security_groups']:
            if sg['name']==sgname:
                neutron.delete_security_group(sg['id'])





