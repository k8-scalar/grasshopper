class Traffic:
    def __init__(self, direction: str, port: int, protocol: str):
        self.direction = direction
        self.port = port
        self.protocol = protocol


class LabelSet:
    def __init__(self, labels: dict[str, str]):
        self.labels = labels


class CIDR:
    def __init__(self, cidr: str):
        self.cidr = cidr


class Policy:
    def __init__(
        self, name: str, sel: LabelSet, allow: tuple[LabelSet | CIDR, Traffic]
    ):
        self.name = name
        self.sel = sel
        self.allow = allow


class SecurityGroup:
    def __init__(self, name: str):
        self.name = name
        self.remotes: set[Rule] = set()


class Pod:
    def __init__(self, label_set: LabelSet):
        self.label_set = label_set


class Rule:
    def __init__(self, target: SecurityGroup | CIDR, traffic: Traffic):
        self.target = target
        self.traffic = traffic


class Node:
    def __init__(self, name):
        self.name = name


class MapEntry:
    def __init__(self):
        self.match_nodes: set[Node] = set()
        self.select_pols: set[Policy] = set()
        self.allow_pols: set[Policy] = set()