from typing import *
from dataclasses import dataclass, field
from bitarray import bitarray
from abc import abstractmethod

@dataclass
class Container:
    name: str
    labels: Dict[str, str]
    nodeName: str
    select_policies: List[int] = field(default_factory=list)
    allow_policies: List[int] = field(default_factory=list)
    select_services: List[int] = field(default_factory=list)
    

    def getValueOrDefault(self, key: str, value: str):
        if key in self.labels:
            return self.labels[key]
        return value

    def getLabels(self):
        return self.labels



@dataclass 
class ServiceSelect:
    labels: Dict[str, str]
    is_allow_all = False
    is_deny_all = False

@dataclass
class Svcprotocol:
    port: Any
    protocol: str
    targetPort: Any = None


@dataclass
class ServicePorts:
    protocol: Svcprotocol
    nodePort: Any = None

T = TypeVar('T')
class LabelRelation(Protocol[T]):
    @abstractmethod
    def match(self, rule: T, value: T) -> bool:
        raise NotImplementedError

class DefaultEqualityLabelRelation(LabelRelation):
    def match(self, rule: Any, value: Any) -> bool:
        return rule == value

@dataclass
class Service:
    name: str
    selector: ServiceSelect
    ports: ServicePorts
    ServiceType: str
    service_select_set: bitarray = None
    matcher: LabelRelation[str] = DefaultEqualityLabelRelation()
    service_select_set: bitarray = None

    @property
    def service_selector(self):
        return self.selector

    def select_service(self, container: Container) -> bool:
        cl = container.labels
        sl = self.service_selector.labels
        for k, v in cl.items():
            if k in sl.keys() and \
                not self.matcher.match(sl[k], v):
                return False
        return True

    def store_svc_bcp(self, select_set: bitarray):
        self.service_select_set = select_set


class ServiceReachability:
    @staticmethod
    def build_svc_matrix(containers: List[Container], services: List[Service]):
        n_container = len(containers)
        n_services = len(services)
        labelMap: Dict[str, bitarray] = DefaultDict(lambda: bitarray('0' * n_container))
        print(containers)

        index_map = [] # Just to know which index to which pod
        for i, service in enumerate(services):
            index_map.append('{}:{}'.format(i,service.name))
        for idx, cont_info in enumerate (containers):
            index_map.append('{}:{}'.format(idx,cont_info.name))
        for i, container in enumerate(containers):
            for key, value in container.labels.items():
                labelMap[key][i] = True
                
        for i, service in enumerate(services):
            select_set = bitarray(n_container)
            select_set.setall(True)

            # work as all direction being egress
            for k, v in service.service_selector.labels.items():
                if k in labelMap.keys(): #all keys in containers
                    select_set &= labelMap[k]

                else:
                    if not service.service_selector.labels:
                        continue
                    select_set.setall(False)

            # dealing with not matched values (needs a customized predicate)
            for idx, cont_info in enumerate (containers):
                if select_set[idx] and not service.select_service(containers[idx]):
                    select_set[idx] = False
           
            service.store_svc_bcp(select_set)

            if service.service_selector.is_allow_all:
                select_set.setall(True)
            elif service.service_selector.is_deny_all:
                select_set.setall(False)           

            for idx in range(n_container):
                if select_set[idx]:
                    containers[idx].select_services.append(i)

        return ServiceReachability(n_container, n_services, index_map)

    def __init__(self, container_size: int, service_size: int, index_map) -> None:
        self.container_size = container_size
        self.service_size = service_size
        self.index_map=index_map
