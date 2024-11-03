from typing import Set

from classes import LabelSet, MapEntry, Node, Pod, Policy, SecurityGroup


pods: Set[Pod] = set()

nodes: Set[Node] = set()

policies: Set[Policy] = set()

Map: dict[LabelSet, MapEntry] = {}

security_groups: dict[str, SecurityGroup] = {}
