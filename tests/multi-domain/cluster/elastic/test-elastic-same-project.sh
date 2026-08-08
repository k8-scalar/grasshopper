#!/usr/bin/env bash
# Verifies Grasshopper dynamically attaches/detaches SG rules as pods matching
# a podSelector-based NetworkPolicy scale in and out, all within one
# OpenStack project - reference-counted per node, not a static snapshot.
#
# Usage: ./test-elastic-same-project.sh
# Requires: kubectl pointed at the cluster, Grasshopper (PNS mode) running,
# config.sh edited to match your cluster's node names/project id.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source config.sh
source lib.sh

NAMESPACE="gh-elastic-test"
A="$PROJECT_A_NODE_1"   # first server node
C="$PROJECT_A_NODE_2"   # scale-out server node
B="$PROJECT_A_NODE_3"   # first client node
D="$PROJECT_A_NODE_4"   # scale-out client node
PORT="$(same_project_port 9090)"

cleanup() {
  kubectl delete namespace "$NAMESPACE" --wait=true >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== Phase 1: baseline (server on $A, client on $B) ==="
kubectl apply -f - >/dev/null <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: $NAMESPACE
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: elastic-test-policy
  namespace: $NAMESPACE
spec:
  podSelector:
    matchLabels:
      app: elastic-server
  policyTypes: ["Ingress"]
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: elastic-client
    ports:
    - protocol: TCP
      port: 9090
---
apiVersion: v1
kind: Pod
metadata:
  name: server-a1
  namespace: $NAMESPACE
  labels:
    app: elastic-server
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
    app: elastic-client
spec:
  nodeName: $B
  containers:
  - name: pause
    image: registry.k8s.io/pause:3.9
EOF
wait_ready pod/server-a1 pod/client-b1 -n "$NAMESPACE"
wait_for_rule_count "server node $A has the ingress rule from client node $B" 1 30 \
  "$PROJECT_A_ID" "$A" "$B" "" "$PORT"

echo "=== Phase 2: scale server out to new node $C ==="
kubectl run server-c1 -n "$NAMESPACE" --image=registry.k8s.io/pause:3.9 \
  --labels=app=elastic-server --overrides="{\"spec\":{\"nodeName\":\"$C\"}}" >/dev/null
wait_ready pod/server-c1 -n "$NAMESPACE"
wait_for_rule_count "new server node $C also gets the rule" 1 30 \
  "$PROJECT_A_ID" "$C" "$B" "" "$PORT"
wait_for_rule_count "original server node $A rule unchanged" 1 5 \
  "$PROJECT_A_ID" "$A" "$B" "" "$PORT"

echo "=== Phase 3: scale server out again, SAME node $A (idempotency) ==="
kubectl run server-a2 -n "$NAMESPACE" --image=registry.k8s.io/pause:3.9 \
  --labels=app=elastic-server --overrides="{\"spec\":{\"nodeName\":\"$A\"}}" >/dev/null
wait_ready pod/server-a2 -n "$NAMESPACE"
wait_for_rule_count "no duplicate rule on $A with a second pod there" 1 15 \
  "$PROJECT_A_ID" "$A" "$B" "" "$PORT"

echo "=== Phase 4: partial scale-in on $A (remove server-a2, server-a1 remains) ==="
kubectl delete pod server-a2 -n "$NAMESPACE" --wait=true >/dev/null
wait_for_rule_count "rule on $A survives - server-a1 still needs it" 1 15 \
  "$PROJECT_A_ID" "$A" "$B" "" "$PORT"

echo "=== Phase 5: full scale-in on $A (remove server-a1 too) ==="
kubectl delete pod server-a1 -n "$NAMESPACE" --wait=true >/dev/null
wait_for_rule_count "rule removed from $A - no server pod left there" 0 15 \
  "$PROJECT_A_ID" "$A" "$B" "" "$PORT"
wait_for_rule_count "rule on $C is untouched by $A's teardown" 1 5 \
  "$PROJECT_A_ID" "$C" "$B" "" "$PORT"

echo "=== Phase 6: scale client out to new node $D ==="
kubectl run client-d1 -n "$NAMESPACE" --image=registry.k8s.io/pause:3.9 \
  --labels=app=elastic-client --overrides="{\"spec\":{\"nodeName\":\"$D\"}}" >/dev/null
wait_ready pod/client-d1 -n "$NAMESPACE"
wait_for_rule_count "server node $C gains a second source entry from $D" 1 15 \
  "$PROJECT_A_ID" "$C" "$D" "" "$PORT"
wait_for_rule_count "...while the entry from $B is still there too" 1 5 \
  "$PROJECT_A_ID" "$C" "$B" "" "$PORT"

echo "=== Phase 7: scale client in - remove original client on $B ==="
kubectl delete pod client-b1 -n "$NAMESPACE" --wait=true >/dev/null
wait_for_rule_count "entry sourced from $B is gone" 0 15 \
  "$PROJECT_A_ID" "$C" "$B" "" "$PORT"
wait_for_rule_count "entry sourced from $D remains" 1 5 \
  "$PROJECT_A_ID" "$C" "$D" "" "$PORT"

echo "=== Phase 8: full teardown ==="
kubectl delete namespace "$NAMESPACE" --wait=true >/dev/null
trap - EXIT
wait_for_rule_count "no leftover rule on $A" 0 15 "$PROJECT_A_ID" "$A" "$B" "" "$PORT"
wait_for_rule_count "no leftover rule on $C" 0 5 "$PROJECT_A_ID" "$C" "$B" "" "$PORT"

report_and_exit
