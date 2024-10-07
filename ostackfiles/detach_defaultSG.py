from credentials import neutron, nova
from kubernetes import client, config
config.load_kube_config()

v1 = client.CoreV1Api()
node_list = v1.list_node()
master_node_name='master'

 
def exception_handler(func):
    def inner_function(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            print(type(e).__name__ + ": " + str(e))
    return inner_function
    
already_created_sgs = []
all_nodes = [node.metadata.name for node in node_list.items]
insgs = neutron.list_security_groups()['security_groups']
for sg_items in insgs:
    already_created_sgs.append(sg_items['name'])  


@exception_handler
def detach():

    for sg_name in already_created_sgs:
        if sg_name == 'default':
            for node_name in all_nodes:
                if node_name != master_node_name:
                    instance = nova.servers.find(name=node_name)
                    try:
                        instance.remove_security_group(sg_name)
                    except:
                        pass

detach()

