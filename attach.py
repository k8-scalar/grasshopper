from neutronclient.v2_0 import client as neutclient
from novaclient import client as novaclient
from credentials import get_nova_creds
creds = get_nova_creds()
nova = novaclient.Client(**creds)
neutron = neutclient.Client(**creds)

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
def attach():
    for sg_name in already_created_sgs:
        if sg_name=='default':
            for node_name in all_nodes:
                if node_name =='master':
                    continue
                if node_name =='client':
                    continue
                instance = nova.servers.find(name=node_name)
                instance.add_security_group(sg_name)
attach()
