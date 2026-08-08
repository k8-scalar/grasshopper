#!/usr/bin/env bash
# Verifies namespaceSelector-based NetworkPolicies: matching is driven by the
# PEER'S NAMESPACE labels (not its own pod labels), scales the same way as
# podSelector-based policies, and a decoy pod with identical pod labels in an
# unlabeled namespace is correctly excluded. Also exercises the documented
# limitation in watchdog.py: an already-matched pod's rule is NOT
# retroactively removed if its namespace's label later changes, but a NEW
# pod created after the change is correctly evaluated against current state.
#
# Usage: ./test-elastic-namespaceselector.sh
# Requires: kubectl pointed at the cluster, Grasshopper (PNS mode) running,
# config.sh edited to match your cluster's node names/project id.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source config.sh
source lib.sh

NS_SERVER="gh-ns-server"
NS_CLIENT="gh-ns-client"
NS_OTHER="gh-ns-other"
A="$PROJECT_A_NODE_1"
C="$PROJECT_A_NODE_2"
B="$PROJECT_A_NODE_3"
D="$PROJECT_A_NODE_4"
PORT="$(same_project_port 9092)"

cleanup() {
  kubectl delete namespace "$NS_SERVER" "$NS_CLIENT" "$NS_OTHER" --wait=true >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== Phase 1: baseline + negative control ==="
echo "    server ($A) selected by podSelector; client ($B, namespace labeled"
echo "    team=platform) selected PURELY by namespace label; decoy ($D, same"
echo "    pod labels as the client but in an UNLABELED namespace) must NOT match."
kubectl apply -f - >/dev/null <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: $NS_SERVER
---
apiVersion: v1
kind: Namespace
metadata:
  name: $NS_CLIENT
  labels:
    team: platform
---
apiVersion: v1
kind: Namespace
metadata:
  name: $NS_OTHER
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: elastic-ns-policy
  namespace: $NS_SERVER
spec:
  podSelector:
    matchLabels:
      app: ns-server
  policyTypes: ["Ingress"]
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          team: platform
    ports:
    - protocol: TCP
      port: 9092
---
apiVersion: v1
kind: Pod
metadata:
  name: server-a1
  namespace: $NS_SERVER
  labels:
    app: ns-server
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
  namespace: $NS_CLIENT
  labels:
    app: whatever-unrelated-label
spec:
  nodeName: $B
  containers:
  - name: pause
    image: registry.k8s.io/pause:3.9
---
apiVersion: v1
kind: Pod
metadata:
  name: decoy-in-other-ns
  namespace: $NS_OTHER
  labels:
    app: whatever-unrelated-label
spec:
  nodeName: $D
  containers:
  - name: pause
    image: registry.k8s.io/pause:3.9
EOF
wait_ready pod/server-a1 -n "$NS_SERVER"
wait_ready pod/client-b1 -n "$NS_CLIENT"
wait_ready pod/decoy-in-other-ns -n "$NS_OTHER"
wait_for_rule_count "server node $A matched via namespace label -> client node $B" 1 30 \
  "$PROJECT_A_ID" "$A" "$B" "" "$PORT"
wait_for_rule_count "decoy on $D (unlabeled namespace, same pod labels) correctly excluded" 0 5 \
  "$PROJECT_A_ID" "$A" "$D" "" "$PORT"

echo "=== Phase 2: scale server out to new node $C ==="
kubectl run server-c1 -n "$NS_SERVER" --image=registry.k8s.io/pause:3.9 \
  --labels=app=ns-server --overrides="{\"spec\":{\"nodeName\":\"$C\"}}" >/dev/null
wait_ready pod/server-c1 -n "$NS_SERVER"
wait_for_rule_count "new server node $C also gets the rule" 1 30 \
  "$PROJECT_A_ID" "$C" "$B" "" "$PORT"

echo "=== Phase 3: scale server out again, SAME node $A (idempotency) ==="
kubectl run server-a2 -n "$NS_SERVER" --image=registry.k8s.io/pause:3.9 \
  --labels=app=ns-server --overrides="{\"spec\":{\"nodeName\":\"$A\"}}" >/dev/null
wait_ready pod/server-a2 -n "$NS_SERVER"
wait_for_rule_count "no duplicate rule on $A" 1 15 "$PROJECT_A_ID" "$A" "$B" "" "$PORT"

echo "=== Phase 4: partial scale-in on $A ==="
kubectl delete pod server-a2 -n "$NS_SERVER" --wait=true >/dev/null
wait_for_rule_count "rule on $A survives" 1 15 "$PROJECT_A_ID" "$A" "$B" "" "$PORT"

echo "=== Phase 5: full scale-in on $A ==="
kubectl delete pod server-a1 -n "$NS_SERVER" --wait=true >/dev/null
wait_for_rule_count "rule removed from $A" 0 15 "$PROJECT_A_ID" "$A" "$B" "" "$PORT"
wait_for_rule_count "rule on $C untouched" 1 5 "$PROJECT_A_ID" "$C" "$B" "" "$PORT"

echo "=== Phase 6: scale client out - second pod in the SAME matching namespace,"
echo "    landing on $D (which already hosts the unrelated decoy pod) ==="
kubectl run client-d1 -n "$NS_CLIENT" --image=registry.k8s.io/pause:3.9 \
  --labels=app=another-unrelated-label --overrides="{\"spec\":{\"nodeName\":\"$D\"}}" >/dev/null
wait_ready pod/client-d1 -n "$NS_CLIENT"
wait_for_rule_count "server node $C gains a second source entry from $D" 1 15 \
  "$PROJECT_A_ID" "$C" "$D" "" "$PORT"
wait_for_rule_count "...while the entry from $B is still there too" 1 5 \
  "$PROJECT_A_ID" "$C" "$B" "" "$PORT"

echo "=== Phase 7: scale client in - remove original client on $B ==="
kubectl delete pod client-b1 -n "$NS_CLIENT" --wait=true >/dev/null
wait_for_rule_count "entry sourced from $B is gone" 0 15 "$PROJECT_A_ID" "$C" "$B" "" "$PORT"
wait_for_rule_count "entry sourced from $D remains (co-located decoy didn't interfere)" 1 5 \
  "$PROJECT_A_ID" "$C" "$D" "" "$PORT"

echo "=== Bonus: remove the matching label from $NS_CLIENT while client-d1 still runs there ==="
kubectl label namespace "$NS_CLIENT" team- >/dev/null
sleep 5
wait_for_rule_count "existing rule from $D persists (documented: not retroactively recomputed)" 1 10 \
  "$PROJECT_A_ID" "$C" "$D" "" "$PORT"

echo "=== Bonus: a NEW pod created in the now-unlabeled namespace must NOT match ==="
kubectl run client-e1 -n "$NS_CLIENT" --image=registry.k8s.io/pause:3.9 \
  --labels=app=post-unlabel-pod --overrides="{\"spec\":{\"nodeName\":\"$A\"}}" >/dev/null
wait_ready pod/client-e1 -n "$NS_CLIENT"
wait_for_rule_count "server node $C does NOT gain an entry from $A (post-relabel pod)" 0 15 \
  "$PROJECT_A_ID" "$C" "$A" "" "$PORT"

echo "=== Phase 8: full teardown ==="
kubectl delete namespace "$NS_SERVER" "$NS_CLIENT" "$NS_OTHER" --wait=true >/dev/null
trap - EXIT
wait_for_rule_count "no leftover rule on $C" 0 15 "$PROJECT_A_ID" "$C" "$D" "" "$PORT"

report_and_exit
