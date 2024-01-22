from credentials import neutron, nova
from kubernetes import client, config

'''def remove_security_groups_by_name(node_name_prefix):
    instances = nova.servers.list()

    for instance in instances:
        for sg in instance.security_groups:
            if sg['name'].startswith(node_name_prefix):
                print(f"detaching {sg['name']} from {instance.name}")
                nova.servers.remove_security_group(instance.id, sg['name'])
                
                # Ask for confirmation before deleting the security group
                confirmation = input(f"Do you want to delete the security group {sg['name']} (y/n)? ").lower()                
                if confirmation == 'y' or confirmation == 'yes':
                
                    security_groups = neutron.list_security_groups(name=sg['name'])
                    for group in security_groups['security_groups']:
                        if group['name'] == sg['name']:
                            security_group_id = group['id']
                            neutron.delete_security_group(security_group_id)  
                else:
                     print(f"Skipping deletion of security group {sg['name']}")               
'''

def remove_security_groups_by_name(node_name_prefix):
    instances = nova.servers.list()

    for instance in instances:
        for sg in instance.security_groups:
            if sg['name'].startswith(node_name_prefix):
                print(f"detaching and deleting {sg['name']}")
                nova.servers.remove_security_group(instance.id, sg['name'])
                security_groups = neutron.list_security_groups(name=sg['name'])
                for group in security_groups['security_groups']:
                    if group['name'] == sg['name']:
                        security_group_id = group['id']
                        neutron.delete_security_group(security_group_id)         

if __name__ == "__main__":
    node_name_prefix = 'SG_'
    remove_security_groups_by_name(node_name_prefix)
