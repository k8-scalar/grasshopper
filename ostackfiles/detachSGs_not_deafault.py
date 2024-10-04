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
def detach():
    worker_pattern = re.compile(r'^worker-(1[0-5]|[1-9])$')

    for sg_name in already_created_sgs:
        if sg_name != 'default' and sg_name != 'workerSG':
            for node_name in all_nodes:
                if worker_pattern.match(node_name):
                    instance = nova.servers.find(name=node_name)
                    try:
                        instance.remove_security_group(sg_name)
                    except:
                        pass

detach()
