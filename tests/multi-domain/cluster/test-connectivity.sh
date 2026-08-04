#!/usr/bin/env bash
# Verifies the thorough-test-app's actual reachability matches what its
# NetworkPolicies allow, against a real deployed cluster. Looks up pod IPs
# live (they change across redeploys) rather than hardcoding them.
#
# Usage: ./test-connectivity.sh
# Requires: kubectl pointed at the cluster, thorough-test-app.yaml already applied.
set -euo pipefail

NAMESPACE="gh-multidomain-thorough"

get_ip() {
  kubectl get pod "$1" -n "$NAMESPACE" -o jsonpath='{.status.podIP}'
}

FRONTEND_IP=$(get_ip app-a-frontend)
BACKEND_IP=$(get_ip app-a-backend)
DATABASE_IP=$(get_ip app-a-database)

echo "frontend=$FRONTEND_IP backend=$BACKEND_IP database=$DATABASE_IP"

check() {
  local desc="$1" from_pod="$2" target_ip="$3" expect="$4"  # expect: allow | block

  if kubectl exec -n "$NAMESPACE" "$from_pod" -- wget -q -T5 -O- "http://$target_ip" >/dev/null 2>&1; then
    result="allow"
  else
    result="block"
  fi

  if [ "$result" == "$expect" ]; then
    echo "[PASS] $desc ($result, as expected)"
  else
    echo "[FAIL] $desc (expected $expect, got $result)"
  fi
}

check "frontend -> backend:80"  app-a-frontend "$BACKEND_IP"  allow
check "backend -> database:80"  app-a-backend  "$DATABASE_IP" allow
check "frontend -> database:80" app-a-frontend "$DATABASE_IP" block
