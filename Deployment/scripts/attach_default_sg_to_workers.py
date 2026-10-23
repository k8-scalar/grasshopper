#!/usr/bin/env python3
"""
Attach the "default" OpenStack security group back to every worker node,
across every OpenStack project this cluster spans.

Why this exists: grasshopper's own startup sequence (main_operator.py ->
detach_defaultSG()) unconditionally strips "default" from every worker node,
relying on process_existing_network_policies() having already opened up
whatever ingress gap each NetworkPolicy needs (e.g. the Typha ipBlock
policy) BEFORE detaching. That rule-generation has a confirmed gap right
now (WORKER_SG_RULES has a Typha egress-to-all rule but no matching
ingress-from-all counterpart, and/or watchdog.handle_new_policy() isn't
picking up the grasshopper-typha-ingress NetworkPolicy correctly) - so
letting grasshopper detach "default" currently leaves calico-node unable to
reach Typha on whichever worker it's scheduled on, which cascades into a
broken BPF dataplane and pod egress silently dropping.

Run this BEFORE (re)starting / scaling the grasshopper Deployment back up,
any time it's been deleted or restarted, until that rule-generation bug is
fixed for real (then this script becomes unnecessary and can be retired).

Mirrors grasshopper's OWN node-to-project grouping exactly (same label,
same "default" project fallback - see classes.py:
node_project_from_labels()/OPENSTACK_PROJECT_NODE_LABEL) rather than
guessing from node-name patterns, so it can't drift out of sync with
whatever grasshopper itself considers a "worker in project X".
"""
import base64
import json
import subprocess
import sys

PROJECT_LABEL = "grasshopper.io/openstack-project"
DEFAULT_PROJECT = "default"
CONTROL_PLANE_LABEL = "node-role.kubernetes.io/control-plane"


def kubectl_json(*args):
    out = subprocess.check_output(["kubectl", *args])
    return json.loads(out)


def get_worker_nodes_by_project():
    nodes = kubectl_json("get", "nodes", "-o", "json")["items"]
    by_project = {}
    for n in nodes:
        labels = n["metadata"].get("labels", {}) or {}
        if CONTROL_PLANE_LABEL in labels:
            continue
        project = labels.get(PROJECT_LABEL, DEFAULT_PROJECT)
        by_project.setdefault(project, []).append(n["metadata"]["name"])
    return by_project


def get_project_credentials():
    b64 = subprocess.check_output([
        "kubectl", "get", "secret", "grasshopper-openstack-creds",
        "-n", "kube-system", "-o", "jsonpath={.data.OS_PROJECTS_JSON}",
    ])
    return {p["key"]: p for p in json.loads(base64.b64decode(b64))}


def attach_default(node_name, creds):
    env_overrides = {
        "OS_AUTH_TYPE": "v3applicationcredential",
        "OS_AUTH_URL": creds["auth_url"],
        "OS_APPLICATION_CREDENTIAL_ID": creds["application_credential_id"],
        "OS_APPLICATION_CREDENTIAL_SECRET": creds["application_credential_secret"],
        "OS_IDENTITY_API_VERSION": "3",
    }
    import os
    env = {**os.environ, **env_overrides}
    result = subprocess.run(
        ["openstack", "server", "add", "security", "group", node_name, "default"],
        env=env, capture_output=True, text=True,
    )
    if result.returncode == 0:
        status = "attached"
    elif "Duplicate items in the list" in result.stderr:
        # Neutron's way of saying "default" is already attached - this is
        # exactly the idempotent/no-op case, not a real failure.
        status = "already attached"
    else:
        status = f"FAILED: {result.stderr.strip()}"
    print(f"  {node_name}: {status}")


def main():
    by_project = get_worker_nodes_by_project()
    creds_by_project = get_project_credentials()

    for project, node_names in by_project.items():
        if project not in creds_by_project:
            print(f"=== project {project}: NO CREDENTIALS FOUND, skipping {len(node_names)} node(s) ===")
            continue
        print(f"=== project {project}: {len(node_names)} worker node(s) ===")
        creds = creds_by_project[project]
        for node_name in node_names:
            attach_default(node_name, creds)

    print("\nDone. Spot-check with:")
    print("  openstack server show <node> -c security_groups -f value")


if __name__ == "__main__":
    sys.exit(main())
