#!/usr/bin/env bash
# Same as test-elastic-same-project.sh, but the server/client pods span two
# different OpenStack projects - exercises the CIDR-of-real-node-IP path
# (Neutron disallows cross-tenant remote_group_id) instead of remote_group_id,
# and confirms the VXLAN port is used unconditionally for cross-project
# traffic regardless of the --intra-project-encapsulation toggle.
#
# Usage: ./test-elastic-cross-project.sh
# Requires: kubectl pointed at the cluster, Grasshopper (PNS mode, multi-domain)
# running, config.sh edited with two real OpenStack projects' node names/ids.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source config.sh
source lib.sh

NAMESPACE="gh-elastic-test-x"
A="$PROJECT_A_NODE_1"   # server node 1 (project A)
C="$PROJECT_A_NODE_2"   # server scale-out node (project A)
B="$PROJECT_B_NODE_1"   # client node 1 (project B)
D="$PROJECT_B_NODE_2"   # client scale-out node (project B)
PORT="$(vxlan_port)"
B_IP="$(node_ip "$B")"
D_IP="$(node_ip "$D")"

cleanup() {
  kubectl delete namespace "$NAMESPACE" --wait=true >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== Phase 1: baseline (server project A/$A, client project B/$B [$B_IP]) ==="
kubectl apply -f - >/dev/null <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: $NAMESPACE
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: elastic-test-x-policy
  namespace: $NAMESPACE
spec:
  podSelector:
    matchLabels:
      app: elastic-x-server
  policyTypes: ["Ingress"]
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: elastic-x-client
    ports:
    - protocol: TCP
      port: 9091
---
apiVersion: v1
kind: Pod
metadata:
  name: server-a1
  namespace: $NAMESPACE
  labels:
    app: elastic-x-server
spec:
  nodeName: $A
  containers:
  - name: pause
    image: registry.k8s.io/pause:3.9
---
apiVersion: v1
kind: Pod
metadata:
  name: client-b1
  namespace: $NAMESPACE
  labels:
    app: elastic-x-client
spec:
  nodeName: $B
  containers:
  - name: pause
    image: registry.k8s.io/pause:3.9
EOF
wait_ready pod/server-a1 pod/client-b1 -n "$NAMESPACE"
wait_for_rule_count "server node $A has a CIDR rule for $B's real IP" 1 30 \
  "$PROJECT_A_ID" "$A" "" "$B_IP/32" "$PORT"
wait_for_rule_count "no stray rule on the client's own node $B" 0 5 \
  "$PROJECT_B_ID" "$B" "" "$B_IP/32" "$PORT"

echo "=== Phase 2: scale server out to new project-A node $C ==="
kubectl run server-c1 -n "$NAMESPACE" --image=registry.k8s.io/pause:3.9 \
  --labels=app=elastic-x-server --overrides="{\"spec\":{\"nodeName\":\"$C\"}}" >/dev/null
wait_ready pod/server-c1 -n "$NAMESPACE"
wait_for_rule_count "new server node $C also gets the CIDR rule" 1 30 \
  "$PROJECT_A_ID" "$C" "" "$B_IP/32" "$PORT"

echo "=== Phase 3: scale server out again, SAME node $A (idempotency) ==="
kubectl run server-a2 -n "$NAMESPACE" --image=registry.k8s.io/pause:3.9 \
  --labels=app=elastic-x-server --overrides="{\"spec\":{\"nodeName\":\"$A\"}}" >/dev/null
wait_ready pod/server-a2 -n "$NAMESPACE"
wait_for_rule_count "no duplicate CIDR rule on $A" 1 15 \
  "$PROJECT_A_ID" "$A" "" "$B_IP/32" "$PORT"

echo "=== Phase 4: partial scale-in on $A ==="
kubectl delete pod server-a2 -n "$NAMESPACE" --wait=true >/dev/null
wait_for_rule_count "rule on $A survives" 1 15 "$PROJECT_A_ID" "$A" "" "$B_IP/32" "$PORT"

echo "=== Phase 5: full scale-in on $A ==="
kubectl delete pod server-a1 -n "$NAMESPACE" --wait=true >/dev/null
wait_for_rule_count "rule removed from $A" 0 15 "$PROJECT_A_ID" "$A" "" "$B_IP/32" "$PORT"
wait_for_rule_count "rule on $C untouched" 1 5 "$PROJECT_A_ID" "$C" "" "$B_IP/32" "$PORT"

echo "=== Phase 6: scale client out to new project-B node $D [$D_IP] ==="
kubectl run client-d1 -n "$NAMESPACE" --image=registry.k8s.io/pause:3.9 \
  --labels=app=elastic-x-client --overrides="{\"spec\":{\"nodeName\":\"$D\"}}" >/dev/null
wait_ready pod/client-d1 -n "$NAMESPACE"
wait_for_rule_count "server node $C gains a second CIDR entry for $D" 1 15 \
  "$PROJECT_A_ID" "$C" "" "$D_IP/32" "$PORT"
wait_for_rule_count "...while $B's entry is still there too" 1 5 \
  "$PROJECT_A_ID" "$C" "" "$B_IP/32" "$PORT"

echo "=== Phase 7: scale client in - remove original client on $B ==="
kubectl delete pod client-b1 -n "$NAMESPACE" --wait=true >/dev/null
wait_for_rule_count "entry for $B's IP is gone" 0 15 "$PROJECT_A_ID" "$C" "" "$B_IP/32" "$PORT"
wait_for_rule_count "entry for $D's IP remains" 1 5 "$PROJECT_A_ID" "$C" "" "$D_IP/32" "$PORT"

echo "=== Phase 8: full teardown ==="
kubectl delete namespace "$NAMESPACE" --wait=true >/dev/null
trap - EXIT
wait_for_rule_count "no leftover rule on $A" 0 15 "$PROJECT_A_ID" "$A" "" "$B_IP/32" "$PORT"
wait_for_rule_count "no leftover rule on $C" 0 5 "$PROJECT_A_ID" "$C" "" "$D_IP/32" "$PORT"

report_and_exit
