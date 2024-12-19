class Traffic:
    def __init__(self, direction: str, port: int, protocol: str):
        self.direction = direction
        self.port = port
        self.protocol = protocol

    def __eq__(self, other):
        if not isinstance(other, Traffic):
            return False
        return (self.direction == other.direction and self.port == other.port and 
               self.protocol == other.protocol)

    def __str__(self):
        return f"Traffic(direction={self.direction}, port={self.port}, protocol={self.protocol})"

    def __eq__(self, other):
        if isinstance(other, Traffic):
            return (
                self.direction == other.direction
                and self.port == other.port
                and self.protocol == other.protocol
            )
        return False


class LabelSet:
    def __init__(self, labels: dict[str, str]):
        self.labels = labels

    def __init__(self):
        self.labels = dict()
        self.string_repr = self.get_string_repr()

    def add_label(key, value):
        self.labels.update({key: value})

    def issubset(self, other):
        return all(
            key in other.labels and other.labels[key] == value
            for key, value in self.labels.items()
        )

    def get_string_repr(self):
        """
        Returns the labelset in string-representation. (as defined in GrassHopper paper.)
        """
        pass

    def __str__(self):
        return f"LabelSet(labels={self.labels})"

    def __eq__(self, other):
        if isinstance(other, LabelSet):
            return self.labels == other.labels
        return False


class CIDR:
    def __init__(self, cidr: str):
        self.cidr = cidr

    def __str__(self):
        return f"CIDR(cidr={self.cidr})"

    def __eq__(self, other):
        if isinstance(other, CIDR):
            return self.cidr == other.cidr
        return False


class Policy:
    def __init__(
        self, name: str, sel: LabelSet, allow: list[tuple[LabelSet | CIDR, Traffic]]
    ):
<<<<<<< Updated upstream
        self.name: str = name
        self.sel: LabelSet = sel
        self.allow: set[tuple[LabelSet | CIDR, Traffic]] = allow
=======
        self.name:  str = name
        self.sel:   LabelSet = sel
        self.allow: list[tuple[LabelSet | CIDR, Traffic]] = allow
<<<<<<< Updated upstream
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes

    def __str__(self):
        allow_str = ", ".join(str(item) for item in self.allow)
        return f"Policy(name={self.name}, sel={self.sel}, allow=[{allow_str}])"

    def __eq__(self, other):
        if isinstance(other, Policy):
            return (
                self.name == other.name
                and self.sel == other.sel
                and self.allow == other.allow
            )
        return False


class SecurityGroup:
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name
        self.remotes: set[Rule] = set()

    def __str__(self):
        remotes_str = ", ".join(str(item) for item in self.remotes)
        return f"SecurityGroup(id={self.id}, name={self.name}, remotes={remotes_str})"

    def __eq__(self, other):
        if isinstance(other, SecurityGroup):
            return self.id == other.id and self.name == other.name
        return False


class Node:
    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return f"Node(name={self.name})"

    def __eq__(self, other):
        if isinstance(other, Node):
            return self.name == other.name
        return False


class Pod:
    def __init__(self, name: str, label_set: LabelSet, node: Node):
        self.name = name
        self.label_set = label_set
        self.node = node

    def is_assigned_to_node(self) -> bool:
        return self.node is not None

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
        # return "------ POD: " + self.name + "-----------\n" + " - Running on node: " + (self.node.name or "None")+ "\n - labels: " + str(json.dumps(self.label_set.labels, indent=4)) + "\n"


class Rule:
    def __init__(self, target: SecurityGroup | CIDR, traffic: Traffic):
        self.target = target
        self.traffic = traffic

    def set_Id(self, id: str):
        self.id = id

    def __str__(self):
        if isinstance(self.target, SecurityGroup):
            target_str = self.target.name
        else:
            target_str = str(self.target)
        return f"Rule(target={target_str}, traffic={self.traffic})"


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
