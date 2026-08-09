#!/usr/bin/env bash
# lib.sh - shared helpers for the elastic-orchestration test scripts in this
# directory. Source config.sh then this file: `source config.sh; source lib.sh`.
# Not run directly.

FAILURES=0

check() {
  local desc="$1" condition="$2"
  if [ "$condition" == "true" ]; then
    echo "[PASS] $desc"
  else
    echo "[FAIL] $desc"
    FAILURES=$((FAILURES + 1))
  fi
}

report_and_exit() {
  echo
  if [ "$FAILURES" -eq 0 ]; then
    echo "ALL CHECKS PASSED"
    exit 0
  else
    echo "$FAILURES CHECK(S) FAILED"
    exit 1
  fi
}

# Runs the python snippet on stdin inside the live Grasshopper pod, with
# access to its openstackfiles/OpenStackClient modules and real OpenStack
# credentials - this is the SAME live state Grasshopper itself is acting on,
# not a mock. `-i` is required: without it, kubectl never forwards this
# call's stdin to the container at all, so `python3 -` reads nothing.
#
# Extra args after the image/container spec are forwarded to the remote
# python process as sys.argv, NOT as environment variables - `kubectl exec`
# does not carry the calling shell's env vars into the container, so a
# caller doing `VAR=x gh_exec_py` would only ever see $VAR locally, never
# inside the pod. Pass values positionally instead: `gh_exec_py "$a" "$b"`,
# read them with `sys.argv[1:]` in the heredoc. Kept as a single-quoted
# heredoc in each caller so bash never tries to expand python's own syntax.
gh_exec_py() {
  # Grasshopper's own code prints diagnostics (e.g. OpenStackClient's
  # "Initializing Openstack Client for project ...") to stdout as a side
  # effect of the very calls these snippets make - always end each snippet
  # with exactly one print() of the value you want, and take only the LAST
  # line here so any such diagnostic noise before it doesn't pollute a
  # caller's `$(...)` capture.
  kubectl exec -i -n "$GH_NAMESPACE" "$GH_POD" -- python3 - "$@" | tail -n 1
}

# Counts security_group_rules on SG_<node> (in the given OpenStack project)
# matching every filter that's non-empty. remote_group_node, if set, is
# resolved to THAT node's own SG id and matched against remote_group_id -
# use this for same-project (SecurityGroup-target) rules. remote_ip_prefix
# is matched exactly - use this for cross-project or ipBlock (CIDR-target)
# rules. port is matched against port_range_min.
sg_rule_count() {
  local project_id="$1" node="$2" remote_group_node="${3:-}" remote_ip_prefix="${4:-}" port="${5:-}"
  gh_exec_py "$project_id" "$node" "$remote_group_node" "$remote_ip_prefix" "$port" <<'PYEOF'
import sys
from openstackfiles.openstack_client import OpenStackClient

project_id, node, remote_group_node, remote_ip_prefix, port = sys.argv[1:6]
remote_group_node = remote_group_node or None
remote_ip_prefix = remote_ip_prefix or None
port = port or None

neutron = OpenStackClient.for_project(project_id).get_neutron()


def sg_id(name):
    return neutron.list_security_groups(name=name)["security_groups"][0]["id"]


sg = neutron.list_security_groups(name=f"SG_{node}")["security_groups"][0]
rules = sg["security_group_rules"]

if remote_group_node:
    target_id = sg_id(f"SG_{remote_group_node}")
    rules = [r for r in rules if r.get("remote_group_id") == target_id]
if remote_ip_prefix:
    rules = [r for r in rules if r.get("remote_ip_prefix") == remote_ip_prefix]
if port:
    rules = [r for r in rules if r.get("port_range_min") == int(port)]

print(len(rules))
PYEOF
}

# Resolves NODE's real internal IP via `kubectl get node`, for cross-project
# tests that need to match a CIDR rule against a specific node's own IP.
node_ip() {
  kubectl get node "$1" -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}'
}

# Polls `sg_rule_count "$@"` (all args forwarded) until it equals
# expected_count or timeout_secs elapses, then asserts equality via check().
# Use this instead of a blind sleep - most phases settle in a couple of
# seconds, but kopf's own retry/backoff can occasionally take longer.
wait_for_rule_count() {
  local desc="$1" expected="$2" timeout_secs="${3:-30}"
  shift 3
  local waited=0 got=-1
  while [ "$waited" -lt "$timeout_secs" ]; do
    got=$(sg_rule_count "$@")
    if [ "$got" == "$expected" ]; then
      break
    fi
    sleep 2
    waited=$((waited + 2))
  done
  check "$desc (expected $expected, got $got after ${waited}s)" "$([ "$got" == "$expected" ] && echo true || echo false)"
}

wait_ready() {
  kubectl wait --for=condition=Ready "$@" --timeout=60s >/dev/null
}

# Same-project pod-to-pod rules use the NetworkPolicy's real port only when
# this deployment's --intra-project-encapsulation is "native" - if it's
# "vxlan", Calico itself encapsulates same-project traffic too, so the port
# actually visible to OpenStack's SG layer is the VXLAN port instead (see
# rule_from() in security_group_module.py). Cross-project rules ALWAYS use
# the VXLAN port regardless of this toggle - callers doing cross-project
# checks should call vxlan_port() directly instead of this.
#
# Reads the setting from the live pod's OWN container args (its actual CLI
# invocation) - NOT by querying network_mode.py's in-process state via a
# fresh `kubectl exec ... python3` process. That can never work: the running
# kopf process sets network_mode.intra_project_encapsulation once, itself, at
# its own startup (see main_operator.py's startup()) - a freshly spawned
# sibling process (exactly what a new exec invocation is) re-imports
# network_mode.py from scratch and only ever sees its hardcoded default
# (native/4789), never whatever the actually-running process configured
# itself with. Confirmed live: this looked like a real encapsulation
# mismatch until checking `kubectl get pod ... -o jsonpath='{.spec.
# containers[0].args}'` directly showed the pod's real args did say vxlan.
_gh_pod_args() {
  kubectl get pod "$GH_POD" -n "$GH_NAMESPACE" -o jsonpath='{.spec.containers[0].args}'
}

same_project_port() {
  local literal_port="$1" args
  args="$(_gh_pod_args)"
  if [[ "$args" == *'"--intra-project-encapsulation","vxlan"'* ]]; then
    vxlan_port
  else
    echo "$literal_port"
  fi
}

# The VXLAN port itself, from the live pod's own args (defaults to 4789,
# Calico's own default, if --vxlan-port wasn't passed explicitly).
vxlan_port() {
  local args
  args="$(_gh_pod_args)"
  if [[ "$args" =~ \"--vxlan-port\",\"([0-9]+)\" ]]; then
    echo "${BASH_REMATCH[1]}"
  else
    echo 4789
  fi
}
