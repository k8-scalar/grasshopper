from contextlib import contextmanager
from time import process_time
from neutronclient.v2_0 import client as neutclient
from novaclient import client as novaclient
from credentials import get_nova_creds
creds = get_nova_creds()
nova = novaclient.Client(**creds)
neutron = neutclient.Client(**creds)

    
@contextmanager
def timing_processtime(description: str) -> None:
    start = process_time()    
    yield
    ellapsed_time = process_time() - start
    print(f"{description}: {ellapsed_time}")
    
    
def removeing_rules_from_SG():
	sgs = neutron.list_security_groups()['security_groups'] # Reload SG list after addition of new SG

	s2 =''
	for sg in sgs:
		if sg['name']=='workerSG':
			s2 = sg
			break

	if s2!='':
		for r in s2['security_group_rules']:
			if r['port_range_min'] == 30007 and \
				r['port_range_max'] == 30007 and \
					r['protocol'] == 'tcp' and \
						r['security_group_id'] == s2['id']:
				neutron.delete_security_group_rule(security_group_rule=r['id'])


removeing_rules_from_SG()




