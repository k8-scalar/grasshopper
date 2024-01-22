import time, yaml, os, ast, pathlib
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from agcp.model_svc import *
from agcp.parser import ConfigParser
from agcp.verify_policy import *
from pprint import pprint
from contextlib import contextmanager
from time import process_time
from config import file_path,singleSGPerNodeScenario
from create_sgpernode import main
from Hmap import h_map  

if singleSGPerNodeScenario:
    user_input = input("\nCheck if per Node SGs are already created? (y/n): ").strip().lower()
    if user_input in ["y", "yes", "Y", "YES"]:
        main()
    else:
        print('\nChecking skipped')
        print('You can now start evaluations\n')

#create eventHandler
if __name__ == "__main__":
    patterns = ["*"]
    ignore_patterns = None
    ignore_directories = False
    case_sensitive = True
    my_event_handler = PatternMatchingEventHandler(patterns, ignore_patterns, ignore_directories, case_sensitive)
    
def offendingPolicies():
    return {'policies':[]}
offenders = offendingPolicies()

def yamlFiles():
    return {}
yamlfiles = yamlFiles()

def initialize_cluster_state():
    return {'policies': [], 'containers': [], 'services': []}

clusterState = initialize_cluster_state()

def update_policy(cluster_state, new_policy):
    existing_policies = cluster_state['policies']
    for pol in new_policy:
        for i, policy in enumerate(existing_policies):      
            if policy.name == pol.name and policy.direction == pol.direction:
                #existing_policies[i] = pol
                break
        else:
            existing_policies.append(pol)

def update_container(cluster_state, containers):
    existing_containers = cluster_state['containers']
    for cont in containers:
        for i, container in enumerate(existing_containers):      
            if container.name == cont.name:
                #existing_containers[i] = cont
                break
        else:
            existing_containers.append(cont)

def update_service(cluster_state, services):
    existing_services = cluster_state['services']
    for serv in services:
        for i, service in enumerate(existing_services):      
            if service.name == serv.name:
                #existing_services[i] = serv
                break
        else:
            existing_services.append(serv)

def update_clusterState(clusterStatefile, cluster_state):
    with open('{}.py'.format(clusterStatefile), 'w') as f:
        f.write("from agcp.model_svc import Container, Policy" + '\n')
        f.write( repr(cluster_state) + '\n')

def update_map(stateMap, newEntry):
    if not stateMap:
        return newEntry
    for key1, value1 in stateMap.items():
        key2 = list(newEntry.keys())[0]
        if key1 == key2:
            stateMap[key1] = newEntry[key2]
        else:
            stateMap.update(newEntry)
    return stateMap
                  

def update_Hmap(Hmapfile, map_entry, event='add'):
    if event=='add':
        if map_entry and map_entry is not None:# and fg_map!=h_map:
            with open('{}.py'.format(Hmapfile), 'w') as f:
                f.write("from agcp.model_svc import PolTraffic, Pol" + '\n')
                f.write("h_map = " + repr(map_entry) + '\n')
    elif event == 'delete':
        if map_entry is not None:
            with open('{}.py'.format(Hmapfile), 'w') as f:
                f.write("from agcp.model_svc import PolTraffic, Pol" + '\n')
                f.write("h_map = " + repr(map_entry) + '\n')

def modify_fg_map_pod(fg_map, sorted_labels, node_name):
    for keyz, values in list(fg_map.items()):
        if ast.literal_eval(keyz).items() <= ast.literal_eval(sorted_labels).items():
            if not values['selPols']: # no policy still selecting it??
                if len(values['selected_Nodes']) ==1 and node_name in values['selected_Nodes']:
                    values['selected_Nodes'].remove(node_name)
                    values['target_SGPerNode_Names'].remove('SG_'+node_name)
                for polz in values['allowPols']:
                    for k, v in list(fg_map.items()):
                        if ast.literal_eval(k).items() == polz.select_labels.items():
                            for rulz in v['allow_section']:
                                if len(rulz.allowedPodsNodes) and node_name in rulz.allowedPodsNodes:
                                    rulz.allowedPodsNodes.remove(node_name)
                    
def modify_fg_map_policy(fg_map, sorted_labels, sel_labels, policyAllow):
    for keyz, values in list(fg_map.items()):
        if ast.literal_eval(keyz).items() == ast.literal_eval(sorted_labels).items():
            for selpol in values['selPols']:
                if selpol.select_labels == sel_labels:
                    values['selPols'].remove(selpol)
                    if not values['selPols'] and not values['allowPols']:
                        del fg_map[keyz]

        #for allowParts in poll[0].allow:
        for allowParts in policyAllow:
            all_labels = allowParts.labels
            sorted_allowLabels = str(dict(OrderedDict(sorted(all_labels.items(), key=lambda kv: kv[0].casefold()))))
            if ast.literal_eval(keyz).items() == ast.literal_eval(sorted_allowLabels).items():
                for polz in values['allowPols']:
                    if polz.select_labels == sel_labels:
                        values['allowPols'].remove(polz)
                if not values['selPols'] and not values['allowPols']:
                    del fg_map[keyz]

#Handle events
@contextmanager
def timing_processtime(description: str) -> None:
    start = process_time()
    yield
    ellapsed_time = process_time() - start
    print(f"{description}: {ellapsed_time}")

def exception_handler(func):
    def inner_function(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            print(type(e).__name__ + ": " + str(e))
    return inner_function

def get_kind(dir_name, yaml_file, event_type):
    with open('{}/{}'.format(dir_name, yaml_file), 'r') as stream:
        try:
            conf = yaml.safe_load(stream)
            print('ResourceType:', conf['kind'])
            print('ResourceName:', conf['metadata']['name'])
            node_name = conf['spec'].get('nodeName')
            if node_name and event_type=='creation':
                print('scheduled to node:', node_name)
            if node_name and event_type=='deletion':
                print('Deleted from node:', node_name)
            return conf['kind'], conf['metadata']['name']
        except yaml.YAMLError as exc:
            print (exc)

'''def get_kind(dir_name, yaml_file, event_type):
    file_path = '{}/{}'.format(dir_name, yaml_file)

    while not os.path.isfile(file_path):
        print("File not yet available:", file_path)

    with open(file_path, 'r') as stream:
        try:
            conf = yaml.safe_load(stream)
            print('ResourceType:', conf['kind'])
            print('ResourceName:', conf['metadata']['name'])
            node_name = conf['spec'].get('nodeName')
            if node_name and event_type == 'creation':
                print('scheduled to node:', node_name)
            if node_name and event_type == 'deletion':
                print('Deleted from node:', node_name)
            return conf['kind'], conf['metadata']['name']
        except yaml.YAMLError as exc:
            print(exc)'''

#watch events
@exception_handler
def on_created(event):
    fg_map={}
    obj_name=os.path.basename(event.src_path)
    file = pathlib.Path(event.src_path)
    print('\nevent: CREATION')
    kind, resourceName = get_kind('data',file.name, 'creation')  
    yamlfiles[file.name] = {'kind':kind, 'resourceName':resourceName}
    if event.is_directory:
        return
    elif kind =='Pod':
        cp = ConfigParser('data/')
        contt, _ ,_= cp.parse('data/{}'.format(obj_name))     
        new_cont_name=contt[0].name
        labels=contt[0].labels
        node_name=contt[0].nodeName
        sorted_labels =str(dict(OrderedDict(sorted(labels.items(), key = lambda kv:kv[0].casefold()))))

        #containers, policies, services = cp.parse()
        containers, _, _ = cp.parse()

        '''update_container(clusterState, contt)
        containers=clusterState['containers']'''
        policies=clusterState['policies']
        services=clusterState['services']
        
        for v in containers:
            if v.name != new_cont_name and  v.labels.items() >=labels.items() and v.nodeName ==node_name:
                print("Pod {} with same (or superset of) labels as pod {} is already attached on node {}".format(v.name, new_cont_name, node_name))
                break
        else:
            #matching with services
            print('Matching with Services')
            with timing_processtime("Time taken"):
                svc_map = ServiceReachability.build_svc(containers, services)
                on_created.svc_map =svc_map
                if svc_map.all_map:
                    ServiceReachability.svc_add_rules(svc_map.all_map)
                else:
                    print("No matching Service")
            update_container(clusterState, containers)
            

            #matching with policies
            print('Matching with policies')
            with timing_processtime("Time taken"):
                all_map= NP_object.build_sgs(contt, policies, InterNode=False)
                if all_map:
                    connections= NP_object.buildconnections(all_map)
                    newMapEntry = NP_object.concate(connections)
                    fg_map=update_map(fg_map, newMapEntry)
                    on_created.map =fg_map
                    if fg_map:
                        pprint (fg_map, sort_dicts=False)
                        SG_object.SGs_and_rules(fg_map, singleSGPerNode=singleSGPerNodeScenario)
                        if not singleSGPerNodeScenario:
                            SG_object.attach_an_sgv2(fg_map,sorted_labels, node_name)
                else:
                    print("No matching Policy")
            update_container(clusterState, containers)


    elif kind == 'NetworkPolicy':  
        cp = ConfigParser('data/') 
        _, poll, _ = cp.parse('data/{}'.format(obj_name)) #Parse the added policy     
        pol_name=poll[0].name
        labels=poll[0].selector.labels
        for items in poll[0].allow:
            all_labels = items.labels.items()
        trafic_dirn = poll[0].direction.direction
        sorted_labels =str(dict(OrderedDict(sorted(labels.items(), key = lambda kv:kv[0].casefold()))))

        #containers, policies, _ = cp.parse()

        #Seems I have to reparse all policies since a policy can affect previous polices
        '''update_policy(clusterState, poll)
        policies=clusterState['policies']'''
        _, policies, _ = cp.parse()
        containers=clusterState['containers']        

        for polz in poll:
            redund= redundant_policy(polz, policies)          
            if redund:
                print(f'\npolicy {polz.name} redandant with: {redund}')
                offenders['policies'].append({polz.name: redund})
                break
            conf= conflicting_policy(polz, policies)           
            if conf:
                print(f'\npolicy {polz.name} conflicting with {conf}')
                offenders['policies'].append({polz.name: conf})
                break
            perm_pols = over_permissive(polz)
            if perm_pols:
                print(f'\npolicy {polz.name} is overpermissive')
                offenders['policies'].append(polz.name)
                break

        if not redund and not conf and not perm_pols:
            for v in policies:
                for items in v.allow:
                    if v.name != pol_name and v.selector.labels.items() ==labels.items() and items.labels.items()==all_labels and v.direction.direction ==trafic_dirn:
                        print("Policy {} with similar set of labels as {} is already applied".format(v.name, pol_name))
                    break
            else:
                with timing_processtime("Time taken"):
                    all_map= NP_object.build_sgs(containers, poll, InterNode=False)
                    if all_map:
                        connections= NP_object.buildconnections(all_map)
                        newMapEntry = NP_object.concate(connections)
                        fg_map=update_map(fg_map, newMapEntry)
                        on_created.map =fg_map                    
                        if fg_map:
                            pprint (fg_map, sort_dicts=False)
                            SG_object.SGs_and_rules(fg_map, singleSGPerNode=singleSGPerNodeScenario)                   
                            if not singleSGPerNodeScenario:
                                SG_object.attach_an_sg(fg_map, sorted_labels)

                update_policy(clusterState, policies)               
            

    elif kind == 'Service':
        cp_serv = ConfigParser('data/')
        _, _, serv = cp_serv.parse('data/{}'.format(obj_name)) #Parse  the added  service
        serv_name=serv[0].name
        labels=serv[0].selector.labels
        sorted_labels =str(dict(OrderedDict(sorted(labels.items(), key = lambda kv:kv[0].casefold()))))       
        
        #containers, _, services= cp_serv.parse()
        _, _, services= cp_serv.parse()
        containers=clusterState['containers']

        for v in services:
            if v.name != serv_name and v.selector.labels.items() ==labels.items():
                print("Service {} with similar set of labels as {} is already applied".format(v.name, serv_name))
        else:
            with timing_processtime("Time taken"):
                svc_map = ServiceReachability.build_svc(containers, services)
                on_created.svc_map =svc_map
                if svc_map.all_map:
                    pprint (vars(svc_map), sort_dicts=False)
                    ServiceReachability.svc_add_rules(svc_map.all_map)
                else:
                    print("No matching Container for the created service")
            update_service(clusterState, services)
    else:
        print('Resource is not container, policy, or service')

    update_clusterState('Cstate', clusterState)
    update_Hmap('Hmap', fg_map, 'add') 


@exception_handler
def on_deleted(event):
    file = pathlib.Path(event.src_path)
    print('\nevent: DELETION')  
    kind = yamlfiles[file.name]['kind']
    resourceName = yamlfiles[file.name]['resourceName']
    print('ResourceType:', kind)
    print('ResourceName:', resourceName)

    if event.is_directory:
        return
    elif kind == 'Pod': 
        for container in clusterState['containers']:
            if container.name == resourceName:
                new_cont_name = container.name
                labels = container.labels
                node_name = container.nodeName
                sorted_labels =str(dict(OrderedDict(sorted(labels.items(), key = lambda kv:kv[0].casefold()))))
        
        #containers, policies, services = cp.parse()
        
        for conts in clusterState['containers']:
            if conts.name !=new_cont_name and conts.nodeName==node_name and conts.labels == labels:
                print("Pod with same labels still running on same node")

        else:          
            try:
                fg_map = on_created.map
            except Exception:
                fg_map = h_map
            with timing_processtime("Time taken"):
                #if pod is on another node dont remove rules from the map
                if conts.name !=new_cont_name and conts.labels == labels:
                    print("Pod with same labels still running on node {}".format(conts.nodeName))
                    if singleSGPerNodeScenario:
                        SG_object.rmv_rules_from_pernodeSG_pod(fg_map,sorted_labels,node_name, False) 
                        modify_fg_map_pod(fg_map, sorted_labels, node_name)
                    else:
                        #No need to remove rules coz the SG is still used on another node
                        SG_object.detach_an_sgvs_pod(fg_map,sorted_labels,node_name, False)

                else:                
                    if not singleSGPerNodeScenario:
                        #can remove rules coz the SG is not used anymore by any node
                        SG_object.detach_an_sgvs_pod(fg_map,sorted_labels,node_name,True)

                        #remove service rules
                        #svc_map = ServiceReachability.build_svc(containers, services)
                        svc_map = on_created.svc_map
                        if svc_map.all_map:
                            for item in svc_map.all_map:
                                if item.selectorLabels == labels:
                                    svc_node_port = item.specPorts.nodePort
                                    ServiceReachability.rmv_rules_from_SG (svc_map.all_map, svc_node_port)

                    if singleSGPerNodeScenario:
                        SG_object.rmv_rules_from_pernodeSG_pod(fg_map,sorted_labels,node_name,True) 
                        modify_fg_map_pod(fg_map, sorted_labels, node_name)
            '''for conts in clusterState['containers']:
                if conts.name == resourceName:
                    clusterState['containers'].remove(conts)'''
            clusterState['containers'] = [conts for conts in clusterState['containers'] if conts.name != resourceName]
                    

    elif kind == 'NetworkPolicy':
        for policy in clusterState['policies']:
            if policy.name == resourceName:
                direction = policy.direction
                sel_labels = policy.selector.labels
                sorted_labels =str(dict(OrderedDict(sorted(sel_labels.items(), key = lambda kv:kv[0].casefold()))))
                policyAllow = policy.allow
        
        try:
            fg_map = on_created.map
        except Exception:
            fg_map = h_map
    
        if not singleSGPerNodeScenario:
            with timing_processtime("Time taken"):
                SG_object.detach_an_sgvs_policy(fg_map,sorted_labels, True)
                #True means that SG shd be deleted
                #False means that only rules should be removed 
            with open('Hmap.py', 'w') as f:
                f.write("from agcp.model_svc import PolTraffic, Pol" + '\n')
                f.write("h_map = {}"  + '\n')

        if singleSGPerNodeScenario:  
            with timing_processtime("Time taken"):
                SG_object.rmv_rules_from_pernodeSG_policy(fg_map,sorted_labels)   
            #Function RemovePolicy from map 
            # can put this outside of time measurements since it does not affect the application 
            modify_fg_map_policy(fg_map, sorted_labels, sel_labels, policyAllow)

            update_Hmap('Hmap', fg_map, 'delete')
            '''for pols in clusterState['policies']:
                if pols.name == resourceName and pols.direction == direction:
                    clusterState['policies'].remove(pols)'''
        clusterState['policies'] = [pols for pols in clusterState['policies'] if pols.name != resourceName]


    elif kind == 'Service':
        for service in clusterState['services']:
            if service.name ==resourceName:
                svc_type = service.ServiceType
                svc_node_port=service.ports.nodePort

        if svc_type == 'NodePort' or svc_node_port !=None:           
            #containers, _, services= cp_serv.parse()
            with timing_processtime("Time taken"):
                #svc_map = ServiceReachability.build_svc(containers, services)
                svc_map=on_created.svc_map
                if svc_map.all_map:
                    ServiceReachability.rmv_rules_from_SG (svc_map.all_map, svc_node_port)
                    ServiceReachability.rmv_rules_from_created_list("workerSG", svc_node_port)
                for servs in clusterState['services']:
                    if servs.name == resourceName:
                        clusterState['services'].remove(servs)
        else:
            print("No rule to remove as service is not of type NodePort")
    else:
        print('Resource is not container, policy, or service')

my_event_handler.on_created = on_created
my_event_handler.on_deleted = on_deleted

#create an observer
path = '{}/data/'.format(file_path)
go_recursively = True
my_observer = Observer()
my_observer.schedule(my_event_handler, path, recursive=go_recursively)

#Start the observer
my_observer.start()
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    my_observer.stop()
    my_observer.join()
