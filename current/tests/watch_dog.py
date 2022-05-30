import time
import pathlib
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from yaml import events
from agcp.model import *
from agcp.algo import *
from agcp.parser import ConfigParser
import yaml
from pprint import pprint
from contextlib import contextmanager
from time import process_time
import os
import ast

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
            print('Resource:', conf['kind'])
            return conf['kind']


        except yaml.YAMLError as exc:
            print (exc)


@exception_handler
def on_created(event):
    obj_name=os.path.basename(event.src_path)
    print(f"{event.src_path} has been created!")
    file = pathlib.Path(event.src_path)
    time.sleep(0.001)#Time to write info from policy evaluated to be 0.0008
    #Still need a more time efficient way to get info from the policy without having to use kubectl get
    kind = get_kind('data',file.name)
    if event.is_directory:
        return
    elif kind =='Pod':
        cp1 = ConfigParser('data/')
        contt, _ = cp1.parse('data/{}'.format(obj_name))
        new_cont_name=contt[0].name
        labels=contt[0].labels
        node_name=contt[0].nodeName
        sorted_labels =str(dict(OrderedDict(sorted(labels.items(), key = lambda kv:kv[0].casefold()))))

        cp = ConfigParser('src_dir/') #* To adjust
        containers, policies = cp.parse()

        for v in containers:
            if v.name != new_cont_name and  v.labels.items() >=labels.items() and v.nodeName ==node_name:
                print("Pod {} with same (or superset of) labels as pod {} is already attached on node {}".format(v.name, new_cont_name, node_name))
                break

        else:
            with timing_processtime("Time taken: "):
                all_map= NP_object.build_sgs(containers, policies, InterNode=False)
                fg_map = NP_object.concate(all_map)
                on_created.map =fg_map
                pprint (fg_map, sort_dicts=False)
                if fg_map:
                    SG_object.SGs_and_rules(fg_map)
                    SG_object.attach_an_sgv2(fg_map,sorted_labels, node_name)
                else:
                    print("No matching Policy found for the created Pod")

    elif kind == 'NetworkPolicy':
        cp1 = ConfigParser('data/')
        _, poll = cp1.parse('data/{}'.format(obj_name)) #Parse the added policy
        pol_name=poll[0].name
        labels=poll[0].selector.labels
        for items in poll[0].allow:
            all_labels = items.labels.items()
        trafic_dirn = poll[0].direction.direction
        sorted_labels =str(dict(OrderedDict(sorted(labels.items(), key = lambda kv:kv[0].casefold()))))

        cp = ConfigParser('src_dir/')
        containers, policies = cp.parse()
        redund= policy_shadow(policies, containers)
        conf= policy_conflict(policies, containers)
        #perm_pols = over_permissive(policies, containers)


        for v in policies:
            #if v.name not in redund and v.name not in conf and not in perm_pols:
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
                    SG_object.SGs_and_rules(fg_map)
                    SG_object.attach_an_sg(fg_map,sorted_labels)
                else:
                    print("No matching Container for the created Policy")

    else:
        print('Resource neither Pod nor Network policy')


'''def on_modified(event):
    print(f"{event.src_path} has been modified")
     if event.is_directory:
        return
    else:
        file = pathlib.Path(event.src_path)
        new_cont_name, labels, node_name=Obj_info(file.name)
        sorted_labels =str(dict(OrderedDict(sorted(labels.items(), key = lambda kv:kv[0].casefold()))))
        print (new_cont_name, sorted_labels)'''

@exception_handler
def on_deleted(event):
    obj_name=os.path.basename(event.src_path)
    print(f"Oops {event.src_path} has been deleted!")
    file = pathlib.Path(event.src_path)
    kind = get_kind('src_dir',file.name)
    if event.is_directory:
        return
    elif kind == 'Pod':
        cp1 = ConfigParser('src_dir/')
        contt, _ = cp1.parse('src_dir/{}'.format(obj_name))
        new_cont_name=contt[0].name
        labels=contt[0].labels
        node_name=contt[0].nodeName
        sorted_labels =str(dict(OrderedDict(sorted(labels.items(), key = lambda kv:kv[0].casefold()))))

        cp = ConfigParser('src_dir/')
        containers, policies = cp.parse()

        for conts in containers:
            if conts.name !=new_cont_name and conts.nodeName==node_name and conts.labels == labels:
                print("Pod {} with same lables as removed {} still running on node {}".format(conts.name, obj_name, conts.nodeName))
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

    elif kind == 'NetworkPolicy':
        cp1 = ConfigParser('src_dir/')
        _, poll = cp1.parse('src_dir/{}'.format(obj_name))
        pol_name=poll[0].name
        labels=poll[0].selector.labels
        #all_labels = poll[0].allow.labels.items()
        #trafic_dirn = poll[0].direction.direction
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
                            for nd_nms in va['node_Name']:
                                SG_object.detach_an_sg(nd_nms,va['SG_name'])
                                SG_object.delete_an_sg(va['SG_name'])
                                print("Security group {} has been detached from node {}".format(va['SG_name'], nd_nms))

                    else:
                        for va in valz:
                            if va['select_labels'] == labels:
                                for nd_nms in va['node_Name']:
                                    SG_object.detach_an_sg(nd_nms,va['SG_name'])
                                    SG_object.delete_an_sg(va['SG_name'])
                                    print("Security group {} has been detached from node {}".format(va['SG_name'], nd_nms))

    else:
        print('Resource neither Pod nor Network policy')

    #Reconstruct the hashmap when a resource is deleted
    '''cp = ConfigParser('data1/')
    containers, policies = cp.parse()
    all_map= NP_object.build_sgs(containers, policies, InterNode=False)
    fg_map = NP_object.concate(all_map)
    with open('Hmap.py','w') as f:
        f.write("h_map= "+ repr(fg_map) + '\n')
    with open('rulz.py','w') as f:
        f.write("already_created_rules=[] "+ '\n')'''
    
    #fg_map = on_deleted.map
    h_map_copy=fg_map.copy()
    for ke, va in h_map_copy.items():
        for vals in va:
            if vals['SG_name'] == sg:
                del fg_map[ke]
                with open('Hmap.py','w') as f:
                    f.write("h_map= "+ repr(fg_map) + '\n')
    
    #Update rulez.py on delete
    from rulz import already_created_rules
    cur_rulz = already_created_rules
    for x in cur_rulz:
        if sg in x:
            cur_rulz.remove(x)
        with open('rulz.py','w') as f:
            f.write("already_created_rules= "+ repr(cur_rulz) + '\n')

my_event_handler.on_created = on_created
my_event_handler.on_deleted = on_deleted
#my_event_handler.on_modified = on_modified

#create an observer
path = "/home/ubuntu/current/data"
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






