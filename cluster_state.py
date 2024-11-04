from classes import *


#Implements Singleton Pattern.
class ClusterState:
    
    map: dict[LabelSet, MapEntry] = {}
    nodes: list[Node] = []
    pods: list[Pod] = []
    policies: list[Policy] = []
    security_groups: dict[str, SecurityGroup] = {}
    
    def __init__(self):
        pass

    @staticmethod
    def getMap():
        return map
    
    @staticmethod
    def addMapEntry(labelSet: LabelSet, mapEntry: MapEntry):
        map.update(labelSet, mapEntry)
    
    @staticmethod
    def getNodes():
        return ClusterState.nodes
    
    @staticmethod
    def addNode(node: Node):
        ClusterState.nodes.append(node)
    
    @staticmethod
    def getPods():
        return ClusterState.pods
    
    @staticmethod
    def addPod(pod: Pod):
        ClusterState.pods.append(pod)
    
    @staticmethod
    def getPolicies():
        return ClusterState.policies
    
    @staticmethod
    def addPolicy(pol: Policy):
        ClusterState.policies.append(pol)

    #print out a nice / clear representation of the cluster state.
    @staticmethod
    def print():
        pass
    
    

    
    