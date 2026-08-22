#!/usr/bin/env bash
# install_grasshopper.sh
# Installs Grasshopper: RBAC, bootstrap NetworkPolicies, then the operator
# pod itself. Run from anywhere - paths below are relative to this script's
# own location, not the caller's working directory.
#
# Usage: ./install_grasshopper.sh [pod-manifest]
#   pod-manifest defaults to pods/grasshopper-operator-PNS.yaml (this
#   script's own directory, i.e. Deployment/), relative or absolute.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

POD_MANIFEST="${1:-pods/grasshopper-operator-PNS.yaml}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}✅${NC} $1"; }
fail() { echo -e "${RED}❌ FAIL${NC}: $1"; exit 1; }
info() { echo -e "${YELLOW}ℹ️  ${NC} $1"; }
hr()   { echo -e "${YELLOW}----------------------------------------${NC}"; }

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
hr
info "Preflight checks..."
command -v kubectl >/dev/null 2>&1 || fail "kubectl not found."
[ -f "rbac/grasshopper-rbac.yaml" ] || fail "rbac/grasshopper-rbac.yaml not found."
[ -d "networkpolicies" ] || fail "networkpolicies/ directory not found."
[ -f "$POD_MANIFEST" ] || fail "Pod manifest '$POD_MANIFEST' not found."
pass "kubectl found, required files present."

# ---------------------------------------------------------------------------
# Step 1: RBAC
# ---------------------------------------------------------------------------
hr
info "Step 1: Applying RBAC..."
kubectl apply -f rbac/grasshopper-rbac.yaml
pass "RBAC applied."

# ---------------------------------------------------------------------------
# Step 2: Bootstrap NetworkPolicies
# ---------------------------------------------------------------------------
# Applies every *.yaml file under networkpolicies/ as-is, substituting a
# small set of well-known placeholder tokens with values discovered live
# from this cluster. This script has no knowledge of what any individual
# policy is FOR (Typha, or anything else a different CNI might need) - it
# only knows how to fill in these tokens if a file happens to use them:
#
#   __NODE_CIDRS__      - replaced with one "- ipBlock: {cidr: <ip>/32}"
#                          entry per node's live InternalIP (not a guessed
#                          subnet - only grants what this cluster's actual
#                          current nodes need).
#   __TYPHA_NAMESPACE__ - replaced with the namespace of a live
#                          k8s-app=calico-typha pod, if this cluster runs
#                          one. A file using this token is skipped entirely
#                          (not applied, not an error) if no such pod is
#                          found - e.g. a non-Calico cluster.
#
# Add a new file here for any other CNI-specific bootstrap policy your
# cluster needs; this script does not need to change to pick it up.
hr
info "Step 2: Applying bootstrap NetworkPolicies..."

NODE_CIDRS_FILE="$(mktemp)"
trap 'rm -f "$NODE_CIDRS_FILE"' EXIT
kubectl get nodes -o jsonpath='{range .items[*]}{range .status.addresses[?(@.type=="InternalIP")]}{.address}{"\n"}{end}{end}' \
    | sed 's/^/      - ipBlock: {cidr: /; s/$/\/32}/' \
    > "$NODE_CIDRS_FILE"
[ -s "$NODE_CIDRS_FILE" ] || fail "Could not discover any node InternalIP - is kubectl pointed at the right cluster?"

TYPHA_NAMESPACE="$(kubectl get pods --all-namespaces -l k8s-app=calico-typha \
    -o jsonpath='{.items[0].metadata.namespace}' 2>/dev/null || true)"

shopt -s nullglob
policy_files=(networkpolicies/*.yaml networkpolicies/*.yml)
if [ ${#policy_files[@]} -eq 0 ]; then
    info "No files in networkpolicies/, skipping."
else
    for f in "${policy_files[@]}"; do
        if grep -q '__TYPHA_NAMESPACE__' "$f" && [ -z "$TYPHA_NAMESPACE" ]; then
            info "Skipping $f: no k8s-app=calico-typha pod found in this cluster."
            continue
        fi
        # Anchored to a line that IS the placeholder (only whitespace around
        # it), not merely containing the string - so a comment that mentions
        # the token by name in prose is never mistaken for the real thing.
        sed -e "/^[[:space:]]*__NODE_CIDRS__[[:space:]]*\$/r $NODE_CIDRS_FILE" \
            -e "/^[[:space:]]*__NODE_CIDRS__[[:space:]]*\$/d" "$f" \
            | sed -e "s/__TYPHA_NAMESPACE__/${TYPHA_NAMESPACE}/g" \
            | kubectl apply -f -
        pass "Applied $f."
    done
fi

# ---------------------------------------------------------------------------
# Step 3: Grasshopper pod
# ---------------------------------------------------------------------------
# Applied last, deliberately after the NetworkPolicies above: Grasshopper's
# own process_existing_network_policies() (run once at its own startup)
# needs every bootstrap-critical policy - Typha's included - to already
# exist by the time it runs, or there's a window where that traffic isn't
# open yet before Grasshopper detaches "default" from workers. See
# README_v2.md for the full explanation of why this ordering matters.
hr
info "Step 3: Applying the Grasshopper pod ($POD_MANIFEST)..."
kubectl apply -f "$POD_MANIFEST"
pass "Grasshopper pod applied."

hr
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Grasshopper installed!${NC}"
echo -e "${GREEN}========================================${NC}"
