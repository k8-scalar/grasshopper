from credentials import neutron, nova
import re

def exception_handler(func):
    def inner_function(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            print(type(e).__name__ + ": " + str(e))
    return inner_function
    
already_created_sgs = []
all_nodes = []
insgs = neutron.list_security_groups()['security_groups']
for sg_items in insgs:
    already_created_sgs.append(sg_items['name'])  

for instance in nova.servers.list():
    all_nodes.append(instance.name)

@exception_handler
def detach_and_delete():
    worker_pattern = re.compile(r'^worker-(1[0-5]|[1-9])$')
    sg_test_pattern = re.compile(r'^SG_policy.*$')

    for sg_name in already_created_sgs:
        if sg_test_pattern.match(sg_name):
            try:
                for group in insgs:
                    if group['name'] == sg_name:
                        security_group_id = group['id']
                        neutron.delete_security_group(security_group_id)  
            except:             
                for node_name in all_nodes:
                    if worker_pattern.match(node_name):
                        instance = nova.servers.find(name=node_name)
                        try:
                            instance.remove_security_group(sg_name)                       
                            for group in insgs:
                                if group['name'] == sg_name:
                                    security_group_id = group['id']
                                    neutron.delete_security_group(security_group_id) 
                        except:
                            pass
detach_and_delete()
