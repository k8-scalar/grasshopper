from credentials import neutron, nova
from kubernetes import client, config

# Load Kubernetes configuration
config.load_kube_config()

# Initialize the Kubernetes API client
v1 = client.CoreV1Api()
node_list = v1.list_node()

# Master node label
master_node_label = 'node-role.kubernetes.io/control-plane'

def exception_handler(func):
    def inner_function(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            print(type(e).__name__ + ": " + str(e))
    return inner_function

already_created_sgs = []
all_nodes = []

# Get the names and labels of all nodes
for node in node_list.items:
    all_nodes.append((node.metadata.name, node.metadata.labels))

# Retrieve existing security groups
insgs = neutron.list_security_groups()['security_groups']
for sg_items in insgs:
    already_created_sgs.append(sg_items['name'])

@exception_handler
def detach():
    for sg_name in already_created_sgs:
        if sg_name == 'default':
            for node_name, labels in all_nodes:
                # Skip nodes with the master label
                if master_node_label in labels:
                    continue  # Skip this node

                # Find the instance by node name and detach the security group
                instance = nova.servers.find(name=node_name)
                try:
                    instance.remove_security_group(sg_name)
                except:
                    pass

# Call the detach function to remove the security group
detach()




