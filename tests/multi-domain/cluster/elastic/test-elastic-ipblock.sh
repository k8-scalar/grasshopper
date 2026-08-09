#!/usr/bin/env bash
# Verifies ipBlock (CIDR) based NetworkPolicies. Architecturally different
# from the other tests here: a CIDR peer is a static address block, not a
# live pod - it never gets a ClusterState.map entry or match-node tracking
# (see the design note in security_group_module.py's rule_from()), and it
# ALWAYS uses the policy's literal port, never the VXLAN port - by design,
# ipBlock is assumed to represent genuinely external, non-VXLAN traffic (see
# create_master_and_workerSG.py's Typha rule for the same pattern live). So
# there's no "peer side" to scale here; the elasticity that DOES apply is
# scaling the selected (target) pods, and reference-counting across multiple
# INDEPENDENT policies that happen to share the same CIDR+port target.
#
# Also regression-tests the Rule.__hash__/__eq__ bug fixed in classes.py: two
# independent policies/pods converging on the same CIDR target on one node
# used to make the second one's rule-creation attempt fail against real
# Neutron (a false-negative in the in-memory dedup check let it try to
# create an already-existing rule) - this exact scenario is phases 6-8 below.
#
# Usage: ./test-elastic-ipblock.sh
# Requires: kubectl pointed at the cluster, Grasshopper (PNS mode) running,
# config.sh edited to match your cluster's node names/project id.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source config.sh
source lib.sh

NAMESPACE="gh-ipblock-test"
A="$PROJECT_A_NODE_1"
C="$PROJECT_A_NODE_2"
CIDR="203.0.113.0/24"   # RFC 5737 TEST-NET-3 - reserved for documentation,
                        # guaranteed to never correspond to a real host.
PORT="9093"             # literal port, always - see the header note above.

cleanup() {
  kubectl delete namespace "$NAMESPACE" --wait=true >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== Phase 1: baseline (server on $A, ipBlock peer $CIDR) ==="
kubectl apply -f - >/dev/null <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: $NAMESPACE
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ipblock-policy-1
  namespace: $NAMESPACE
spec:
  podSelector:
    matchLabels:
      app: ipblock-server
  policyTypes: ["Ingress"]
  ingress:
  - from:
    - ipBlock:
        cidr: $CIDR
    ports:
    - protocol: TCP
      port: $PORT
---
apiVersion: v1
kind: Pod
metadata:
  name: server-a1
  namespace: $NAMESPACE
  labels:
    app: ipblock-server
spec:
  nodeName: $A
  containers:
  - name: pause
    image: registry.k8s.io/pause:3.9
EOF
wait_ready pod/server-a1 -n "$NAMESPACE"
wait_for_rule_count "server node $A has the CIDR rule, literal port $PORT" 1 30 \
  "$PROJECT_A_ID" "$A" "" "$CIDR" "$PORT"

echo "=== Phase 2: scale server out to new node $C ==="
kubectl run server-c1 -n "$NAMESPACE" --image=registry.k8s.io/pause:3.9 \
  --labels=app=ipblock-server --overrides="{\"spec\":{\"nodeName\":\"$C\"}}" >/dev/null
wait_ready pod/server-c1 -n "$NAMESPACE"
wait_for_rule_count "new server node $C also gets the CIDR rule" 1 30 \
  "$PROJECT_A_ID" "$C" "" "$CIDR" "$PORT"

echo "=== Phase 3: scale server out again, SAME node $A (idempotency) ==="
kubectl run server-a2 -n "$NAMESPACE" --image=registry.k8s.io/pause:3.9 \
  --labels=app=ipblock-server --overrides="{\"spec\":{\"nodeName\":\"$A\"}}" >/dev/null
wait_ready pod/server-a2 -n "$NAMESPACE"
wait_for_rule_count "no duplicate CIDR rule on $A" 1 15 "$PROJECT_A_ID" "$A" "" "$CIDR" "$PORT"

echo "=== Phase 4: partial scale-in on $A ==="
kubectl delete pod server-a2 -n "$NAMESPACE" --wait=true >/dev/null
wait_for_rule_count "rule on $A survives" 1 15 "$PROJECT_A_ID" "$A" "" "$CIDR" "$PORT"

echo "=== Phase 5: full scale-in on $A ==="
kubectl delete pod server-a1 -n "$NAMESPACE" --wait=true >/dev/null
wait_for_rule_count "rule removed from $A" 0 15 "$PROJECT_A_ID" "$A" "" "$CIDR" "$PORT"
wait_for_rule_count "rule on $C untouched" 1 5 "$PROJECT_A_ID" "$C" "" "$CIDR" "$PORT"

echo "=== Phase 6: second, INDEPENDENT policy + pod sharing the same CIDR+port"
echo "    target, landing on the SAME node $C as server-c1 - this is the exact"
echo "    scenario that used to fail against real Neutron (see header note) ==="
kubectl apply -f - >/dev/null <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ipblock-policy-2
  namespace: $NAMESPACE
spec:
  podSelector:
    matchLabels:
      app: ipblock-server-2
  policyTypes: ["Ingress"]
  ingress:
  - from:
    - ipBlock:
        cidr: $CIDR
    ports:
    - protocol: TCP
      port: $PORT
---
apiVersion: v1
kind: Pod
metadata:
  name: server2-c1
  namespace: $NAMESPACE
  labels:
    app: ipblock-server-2
spec:
  nodeName: $C
  containers:
  - name: pause
    image: registry.k8s.io/pause:3.9
EOF
wait_ready pod/server2-c1 -n "$NAMESPACE"
wait_for_rule_count "still exactly one rule on $C (correctly deduplicated, no Neutron conflict)" 1 15 \
  "$PROJECT_A_ID" "$C" "" "$CIDR" "$PORT"

echo "=== Phase 7: delete policy-1 - rule must survive because policy-2 still needs it ==="
kubectl delete networkpolicy ipblock-policy-1 -n "$NAMESPACE" --wait=true >/dev/null
wait_for_rule_count "rule on $C survives policy-1's removal" 1 15 "$PROJECT_A_ID" "$C" "" "$CIDR" "$PORT"

echo "=== Phase 8: delete policy-2 too - now nothing needs the rule ==="
kubectl delete networkpolicy ipblock-policy-2 -n "$NAMESPACE" --wait=true >/dev/null
wait_for_rule_count "rule on $C finally removed" 0 15 "$PROJECT_A_ID" "$C" "" "$CIDR" "$PORT"

echo "=== Phase 9: full teardown ==="
kubectl delete namespace "$NAMESPACE" --wait=true >/dev/null
trap - EXIT
wait_for_rule_count "no leftover rule on $A" 0 15 "$PROJECT_A_ID" "$A" "" "$CIDR" "$PORT"
wait_for_rule_count "no leftover rule on $C" 0 5 "$PROJECT_A_ID" "$C" "" "$CIDR" "$PORT"

report_and_exit
