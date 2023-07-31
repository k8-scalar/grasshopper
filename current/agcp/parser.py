import time
from .model_svc import *
from yaml import load
import os
import yaml
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


class ConfigParser:
    def __init__(self, filepath=None):
        self.filepath = filepath
        self.containers = []
        self.policies = []
        self.services = []

    def parse(self, filepath=None):
        if filepath == None:
            filepath = self.filepath

        if filepath == None:
            print('no filepath specified')
            return

        if os.path.isfile(filepath):
            try:
                with open(filepath, 'r') as f:
                    data = yaml.safe_load(f)
                    # Process the loaded data or create an object
                    self.create_object(data)
            except FileNotFoundError:
                print("File not found: " + filepath)
            except IOError:
                print("Error reading file: " + filepath)
            except yaml.YAMLError as e:
                print("Error parsing YAML file: " + str(e))

        else:

            try:
                time.sleep(0.001)#Time to write yaml to data evaluated to be 0.0008
                for subdir, dirs, files in os.walk(filepath):
                    for file in files:
                        filename = os.path.join(subdir, file)

                        with open(filename) as f:
                            data = load(f, Loader=Loader)
                            self.create_object(data)
            except:
                print("Error opening or reading directory")
                raise

        return self.containers, self.policies, self.services

    def create_object(self, data):

        if data['kind'] == 'NetworkPolicy':
            try:
                select = data['spec']['podSelector']['matchLabels']
            except KeyError:
                select = {}
            if 'Ingress' in data['spec']['policyTypes']:
                
                for ing in data['spec']['ingress']:
                    allow = []
                    ports = None
                    cidr = None
                    for f in ing['from']:
                        if 'podSelector' in f:
                            allow_labels=(f['podSelector']['matchLabels'])
                            allow_labels= PolicyAllow(allow_labels)
                            allow.append(allow_labels)
                        if 'ipBlock' in f:
                            cidr = (f['ipBlock']['cidr'])

                    if 'ports' in ing:
                        for p in ing['ports']:
                            if 'protocol' in p:
                                if 'port' in p:
                                    ports = [p['protocol'], p['port'], p['port']]#port_min =port_max if one port is opened in the policy

                    new_policy = Policy(data['metadata']['name'], PolicySelect(select), allow, PolicyIngress, ports, cidr)
                    self.policies.append(new_policy)


            if 'Egress' in data['spec']['policyTypes']:
                for eg in data['spec']['egress']:
                    allow = []
                    ports = None
                    cidr = None
                    for t in eg['to']:
                        if 'podSelector' in t:
                            allow_labels=(t['podSelector']['matchLabels'])
                            allow_labels= PolicyAllow(allow_labels)
                            allow.append(allow_labels)
                        if 'ipBlock' in t:
                            cidr = (t['ipBlock']['cidr'])
                    if 'ports' in eg:
                        for p in eg['ports']:
                            if 'protocol' in p:
                                if 'port' in p:
                                    ports = [p['protocol'], p['port'], p['port']]

                    new_policy = Policy(data['metadata']['name'], PolicySelect(select), allow, PolicyEgress, ports,cidr)
                    if new_policy not in self.policies:
                        self.policies.append(new_policy)

        elif data['kind'] == 'Service':
            protocol_list =[]
            nodePort=None
            try:
                select = data['spec']['selector']
            except KeyError:
                select = {}
                
            for sec in data['spec']['ports']:
                if 'protocol' in sec:
                    protocol=sec['protocol']
                else:
                    protocol='TCP'
                if 'targetPort' in sec:
                    targetPort=sec['targetPort']
                else:
                    targetPort=None
                if 'nodePort' in sec:
                    nodePort=sec['nodePort']
                else:
                    nodePort=None
                port = sec['port']
                protocol_list.append(Svcprotocol(port, protocol, targetPort))
            if 'type' in data['spec']:
                svc_type= data['spec']['type']
            else:
                svc_type= 'ClusterIP'
                
            new_service = Service(data['metadata']['name'], ServiceSelect(select), ServicePorts(protocol_list ,nodePort), svc_type)
            if new_service not in self.services:
                self.services.append(new_service)

        elif data['kind'] == 'Pod':
            labels = data['metadata']['labels']
            new_container = Container(data['metadata']['name'], labels, data['spec']['nodeName'])
            if new_container not in self.containers:
                self.containers.append(new_container)


    def print_all(self):
        for c in self.containers:
            print(c)
        for p in self.policies:
            print(p)
        for s in self.services:
            print(s)

def main():
   cp = ConfigParser()
   cp.parse('data')
   cp.print_all()

if __name__ == '__main__':
    main()


