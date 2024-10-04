from credentials import neutron, nova
from kubernetes import client, config

def get_k8s_nodes():
    config.load_kube_config()
    v1 = client.CoreV1Api()

    try:
        nodes_list = v1.list_node().items
        return nodes_list
    except Exception as e:
        print("Error while retrieving nodes:", e)
        return []

def get_security_group(neutron, sg_name):
    try:
        sg_list = neutron.list_security_groups(name=sg_name)['security_groups']
        if sg_list:
            return sg_list[0]  # Return the first security group with the specified name
    except Exception as e:
        print("Error while retrieving security group:", e)
    return None

def create_security_group(neutron, node_name):
    sg_name = 'SG_' + node_name
    sg_description = 'Security group for ' + node_name

    existing_sg = get_security_group(neutron, sg_name)
    '''if existing_sg:
        print(f"Security group {sg_name} already exists")
        return existing_sg
    else:
        body = {
            'security_group': {
                'name': sg_name,
                'description': sg_description
            }
        }

        try:
            security_group = neutron.create_security_group(body=body)['security_group']
            return security_group
        except Exception as e:
            print("Error while creating security group:", e)
            return None'''
    if not existing_sg:
        body = {
            'security_group': {
                'name': sg_name,
                'description': sg_description
            }
        }
        security_group = neutron.create_security_group(body=body)['security_group']
        print(f"Creating and attaching SG_{node_name}")
        return security_group
    else:
        return existing_sg
       

def get_server_id_by_name(node_name):
    instances = nova.servers.list()
    for instance in instances:
        if instance.name == node_name:
            return instance.id

def attach_security_group(node_name, security_group):
    server_id = get_server_id_by_name(node_name)

    # Check if the security group is already attached to the server
    server = nova.servers.get(server_id)
    attached_security_groups = [sg['name'] for sg in server.security_groups]
    '''if 'SG_'+node_name in attached_security_groups:  
        print(f"Security group already attached to '{node_name}'.")
    else:
        nova.servers.add_security_group(server_id, security_group)'''
    if 'SG_'+node_name not in attached_security_groups:  
        nova.servers.add_security_group(server_id, security_group)


def main():
    nodes = get_k8s_nodes()
    if nodes:
        print('\nchecking if per Node SGs are already created and attached\n')
        for node in nodes:
            node_name = node.metadata.name  
            print(f'checking node {node_name}')        
            security_group = create_security_group(neutron, node_name)
            for r in security_group['security_group_rules']:
                neutron.delete_security_group_rule(security_group_rule=r['id'])
            attach_security_group(node_name, security_group['id'])
        print('\nFinished checking SGs')
        print('You can now start evaluations')
    else:
        print("No nodes found in the cluster.")

if __name__ == '__main__':
    main()

