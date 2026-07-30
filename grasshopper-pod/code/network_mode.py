"""
Global config for the multi-domain network toggle. Kept in its own module
(rather than main_operator.py) so security_group_module.py can read it without
a circular import back into the operator entrypoint.
"""

ENCAPSULATION_NATIVE = "native"
ENCAPSULATION_VXLAN = "vxlan"

# Whether same-project connections are native-routed (today's default,
# unchanged behavior) or also VXLAN-encapsulated. Cross-project connections
# always require VXLAN regardless of this setting - see security_group_module.py.
intra_project_encapsulation = ENCAPSULATION_NATIVE

# Calico's default VXLAN encapsulation port.
vxlan_port = 4789


def configure(encapsulation: str, port: int):
    global intra_project_encapsulation, vxlan_port
    if encapsulation not in (ENCAPSULATION_NATIVE, ENCAPSULATION_VXLAN):
        raise ValueError(f"Unknown encapsulation mode: {encapsulation}")
    intra_project_encapsulation = encapsulation
    vxlan_port = port
