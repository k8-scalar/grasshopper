import re
from credentials import neutron
secgroups = neutron.list_security_groups()['security_groups']
for secgroup in secgroups:
    if re.match(r'SG_worker-[1-9]|1[0-5]$', secgroup['name']):
        for rule in secgroup['security_group_rules']:
            neutron.delete_security_group_rule(security_group_rule=rule['id'])
