import time
import pathlib
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from agcp.model_svc import *
from agcp.parser import ConfigParser
from agcp.verify_policy import *
import yaml
from pprint import pprint
from contextlib import contextmanager
from time import process_time
import os
import ast
from credentials import neutron, nova
from config import file_path,singleSGPerNodeScenario
from create_sgpernode import main

if singleSGPerNodeScenario:
    main()

#create eventHandler
if __name__ == "__main__":
    patterns = ["*"]
    ignore_patterns = None
    ignore_directories = False
    case_sensitive = True
    my_event_handler = PatternMatchingEventHandler(patterns, ignore_patterns, ignore_directories, case_sensitive)

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

def get_kind(dir_name, yaml_file):
    with open('{}/{}'.format(dir_name, yaml_file), 'r') as stream:
        try:
            conf = yaml.safe_load(stream)
            print('ResourceType:', conf['kind'])
            return conf['kind']
        except yaml.YAMLError as exc:
            print (exc)


#watch events
#@exception_handler
def on_created(event):
    obj_name=os.path.basename(event.src_path)
    file = pathlib.Path(event.src_path)
    print(f"{file.name} applied to the cluster")
    kind = get_kind('data',file.name)
    if event.is_directory:
        return
    elif kind =='Pod':
        contt, _ ,_= ConfigParser('data/{}'.format(obj_name)).parse()      
        new_cont_name=contt[0].name
        labels=contt[0].labels
        node_name=contt[0].nodeName
        sorted_labels =str(dict(OrderedDict(sorted(labels.items(), key = lambda kv:kv[0].casefold()))))
        cp = ConfigParser('data/')
        containers, policies, services = cp.parse()

        for v in containers:
            if v.name != new_cont_name and  v.labels.items() >=labels.items() and v.nodeName ==node_name:
                print("Pod {} with same (or superset of) labels as pod {} is already attached on node {}".format(v.name, new_cont_name, node_name))
                break
        else:
            #matching with services
            with timing_processtime("Time taken to match with services: "):
                svc_map = ServiceReachability.build_svc(containers, services)
                if svc_map.all_map:
                    ServiceReachability.svc_add_rules(svc_map.all_map)
                else:
                    print("No matching Service found for the created Pod")

            #matching with policies
            with timing_processtime("Time taken to match with policies: "):
                all_map= NP_object.build_sgs(containers, policies, InterNode=False)
                fg_map = NP_object.concate(all_map)
                on_created.map =fg_map
                pprint (fg_map, sort_dicts=False)
                if fg_map:
                    SG_object.SGs_and_rules(fg_map, singleSGPerNode=singleSGPerNodeScenario)
                    if not singleSGPerNodeScenario:
                        SG_object.attach_an_sgv2(fg_map,sorted_labels, node_name)
                #else:
                    #print("No matching Policy found for the created Pod")

    elif kind == 'NetworkPolicy':        
        _, poll, _ = ConfigParser('data/{}'.format(obj_name)).parse() #Parse the added policy
        print(poll)
        pol_name=poll[0].name
        labels=poll[0].selector.labels
        for items in poll[0].allow:
            all_labels = items.labels.items()
        trafic_dirn = poll[0].direction.direction
        sorted_labels =str(dict(OrderedDict(sorted(labels.items(), key = lambda kv:kv[0].casefold()))))
        cp = ConfigParser('data/')
        containers, policies, _ = cp.parse()
        for polz in poll:
            redund= redundant_policy(polz, policies)
            print('redandant with: ',redund)
            conf= conflicting_policy(polz, policies)
            print('conflicting with: ',conf)
            perm_pols = over_permissive(polz)
            print(perm_pols)
        if not redund and not conf and not perm_pols:
            for v in policies:
                for items in v.allow:
                    if v.name != pol_name and v.selector.labels.items() ==labels.items() and items.labels.items()==all_labels and v.direction.direction ==trafic_dirn:
                        print("Policy {} with similar set of labels as {} is already applied".format(v.name, pol_name))
                    break
            else:
                with timing_processtime("Time taken: "):
                    all_map= NP_object.build_sgs(containers, policies, InterNode=False)
                    fg_map = NP_object.concate(all_map)
                    on_created.map =fg_map
                    pprint (fg_map, sort_dicts=False)
                    if fg_map:
                        SG_object.SGs_and_rules(fg_map, singleSGPerNode=singleSGPerNodeScenario)                   
                        if not singleSGPerNodeScenario:
                            SG_object.attach_an_sg(fg_map, sorted_labels)
                    #else:
                        #print("No matching Container for the created Policy")

    elif kind == 'Service':
        _, _, serv = ConfigParser('data/{}'.format(obj_name)).parse() #Parse  the added  service
        serv_name=serv[0].name
        labels=serv[0].selector.labels
        sorted_labels =str(dict(OrderedDict(sorted(labels.items(), key = lambda kv:kv[0].casefold()))))
        cp_serv = ConfigParser('data/')
        containers, _, services= cp_serv.parse()

        for v in services:
            if v.name != serv_name and v.selector.labels.items() ==labels.items():
                print("Service {} with similar set of labels as {} is already applied".format(v.name, serv_name))
        else:
            with timing_processtime("Time taken: "):
                svc_map = ServiceReachability.build_svc(containers, services)

                pprint (vars(svc_map), sort_dicts=False)
                if svc_map.all_map:
                    ServiceReachability.svc_add_rules(svc_map.all_map)
                else:
                    print("No matching Container for the created service")
    else:
        print('Resource is not container, policy, or service')


#@exception_handler
def on_deleted(event):
    obj_name=os.path.basename(event.src_path)
    file = pathlib.Path(event.src_path)
    #print(f"Oops {file.name} has been deleted!")   
    kind = get_kind('src_dir',file.name)
    if event.is_directory:
        return
    elif kind == 'Pod':  
        contt, _,_ = ConfigParser('src_dir/{}'.format(obj_name)).parse()
        new_cont_name=contt[0].name
        labels=contt[0].labels
        node_name=contt[0].nodeName
        sorted_labels =str(dict(OrderedDict(sorted(labels.items(), key = lambda kv:kv[0].casefold()))))
        cp = ConfigParser('src_dir/')
        containers, policies, services = cp.parse()

        for conts in containers:
            if conts.name !=new_cont_name and conts.nodeName==node_name and conts.labels == labels:
                print("Pod {} with same lables as removed {} still running on node {}".format(conts.name, obj_name, conts.nodeName))
            elif conts.name !=new_cont_name and conts.labels == labels:
                print("Pod {} with same lables as removed {} still running in the cluster on node {}".format(conts.name, obj_name, conts.nodeName))
                break

        else:
            with timing_processtime("Time taken: "):
                try:
                    fg_map = on_created.map
                except Exception:
                    from Hmap import h_map
                    fg_map = h_map
                for ke, valz in fg_map.items():
                    if ast.literal_eval(sorted_labels).items() >= ast.literal_eval(ke).items():
                        if len(valz) ==1:
                            for va in valz:
                                SG_object.detach_an_sg(node_name,va['SG_name'])
                                #SG_object.delete_an_sg(va['SG_name'])
                                print("Security group {} has been detached from node {}".format(va['SG_name'], node_name))
                        else:
                            for va in valz:
                                if va['select_labels'] == labels:
                                    SG_object.detach_an_sg(node_name,va['SG_name'])
                                    #SG_object.delete_an_sg(va['SG_name'])
                                    print("Security group {} has been detached from node {}".format(va['SG_name'], node_name))

                #remove service rules
                svc_map = ServiceReachability.build_svc(containers, services)
                if svc_map.all_map:
                    for item in svc_map.all_map:
                        if item.selectorLabels == labels:
                            svc_node_port = item.specPorts.nodePort
                            ServiceReachability.rmv_rules_from_SG (svc_map.all_map, svc_node_port)

    elif kind == 'NetworkPolicy':
        cp = ConfigParser('src_dir/')
        _, poll, _ = ConfigParser('src_dir/{}'.format(obj_name)).parse()
        labels=poll[0].selector.labels
        sorted_labels =str(dict(OrderedDict(sorted(labels.items(), key = lambda kv:kv[0].casefold()))))
        try:
            fg_map = on_created.map
        except Exception:
            from Hmap import h_map
            fg_map = h_map
        with timing_processtime("Time taken: "):
            for ke, valz in fg_map.items():
                if ast.literal_eval(sorted_labels).items() <= ast.literal_eval(ke).items():
                    if len(valz) ==1:
                        for va in valz:
                            if va['selected_Nodes'] !=None:
                                for nd_nms in va['selected_Nodes']:
                                    SG_object.detach_an_sg(nd_nms,va['SG_name'])
                                    SG_object.delete_an_sg(va['SG_name'])
                                    print("Security group {} has been detached from node {}".format(va['SG_name'], nd_nms))
                                    SG_object.rmv_rules_from_created_list(va['SG_name']) # when commented seems not to work well.
                                    for items in va['allow_section']:
                                        SG_object.rmv_rules(va['SG_name'], items.traffic, items.proto, items.port, items.cidr)
                                        if va['RemoteSG_role']:
                                            for itemz in va['AllowLabels_SG_name']:
                                                SG_object.rmv_rules_rmsg(va['SG_name'], items.traffic, items.proto, items.port, items.cidr, itemz)                                       

                    else:
                        for va in valz:
                            if va['select_labels'] == labels:
                                for nd_nms in va['selected_Nodes']:
                                    SG_object.detach_an_sg(nd_nms,va['SG_name'])
                                    SG_object.delete_an_sg(va['SG_name'])
                                    print("Security group {} has been detached from node {}".format(va['SG_name'], nd_nms))
                                    SG_object.rmv_rules_from_created_list(va['SG_name'])
                                for items in va['allow_section']:
                                    SG_object.rmv_rules(va['SG_name'], items.traffic, items.proto, items.port, items.cidr)
                                    if va['RemoteSG_role']:
                                        for itemz in va['AllowLabels_SG_name']:
                                            print('tttttt',itemz)
                                            SG_object.rmv_rules_rmsg(va['SG_name'], items.traffic, items.proto, items.port, items.cidr, itemz)                                       

    elif kind == 'Service':
        _, _, serv = ConfigParser('src_dir/{}'.format(obj_name)).parse()
        svc_type = serv[0].ServiceType
        svc_node_port=serv[0].ports.nodePort
        if svc_type == 'NodePort' or svc_node_port !=None:
            cp_serv = ConfigParser('src_dir/')
            containers, _, services= cp_serv.parse()
            with timing_processtime("Time taken: "):
                svc_map = ServiceReachability.build_svc(containers, services)
                if svc_map.all_map:
                    ServiceReachability.rmv_rules_from_SG (svc_map.all_map, svc_node_port)
                    ServiceReachability.rmv_rules_from_created_list("workerSG", svc_node_port)
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

