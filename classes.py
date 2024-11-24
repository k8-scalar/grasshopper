class Traffic:
    def __init__(self, direction: str, port: int, protocol: str):
        self.direction = direction
        self.port = port
        self.protocol = protocol

    def __str__(self):
        return f"Traffic(direction={self.direction}, port={self.port}, protocol={self.protocol})"


class LabelSet:
    def __init__(self, labels: dict[str, str]):
        self.labels = labels

    def issubset(self, other):
        return all(
            key in other.labels and other.labels[key] == value
            for key, value in self.labels.items()
        )

    def __str__(self):
        return f"LabelSet(labels={self.labels})"


class CIDR:
    def __init__(self, cidr: str):
        self.cidr = cidr

    def __str__(self):
        return f"CIDR(cidr={self.cidr})"


class Policy:
    def __init__(
        self, name: str, sel: LabelSet, allow: tuple[LabelSet | CIDR, Traffic]
    ):
        self.name = name
        self.sel = sel
        self.allow = allow

    def __str__(self):
        return f"Policy(name={self.name}, sel={self.sel}, allow={self.allow})"


class SecurityGroup:
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name
        self.remotes: set[Rule] = set()

    def __str__(self):
        return f"SecurityGroup(id={self.id}, name={self.name}, remotes={self.remotes})"


class Node:
    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return f"Node(name={self.name})"


class Pod:
    def __init__(self, name: str, label_set: LabelSet, node: Node):
        self.name = name
        self.label_set = label_set
        self.node = node

    @staticmethod
    def from_dict(data: dict):
        name = data.get("name")
        labels = data.get("label_set", {}).get("labels", {})
        label_set = LabelSet(labels=labels)
        node_name = data.get("node", {}).get("name")
        node = Node(node_name)
        return Pod(
            name,
            label_set,
            node,
        )

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, Pod):
            return self.name == other.name
        return False

    def __str__(self):
        return f"Pod(name={self.name}, label_set={self.label_set}, node={self.node}"


class Rule:
    def __init__(self, target: SecurityGroup | CIDR, traffic: Traffic):
        self.target = target
        self.traffic = traffic

    def set_Id(self, id: str):
        self.id = id

    def __str__(self):
        return f"Rule(target={self.target}, traffic={self.traffic})"


class MapEntry:
    def __init__(self):
        self.match_nodes: set[Node] = set()
        self.select_pols: set[Policy] = set()
        self.allow_pols: set[Policy] = set()

    def __str__(self):
        return (
            f"MapEntry(match_nodes={self.match_nodes}, "
            f"select_pols={self.select_pols}, allow_pols={self.allow_pols})"
        )
