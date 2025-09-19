#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

kubectl apply -f "$SCRIPT_DIR/yamls/allow-application-pods.yaml"
kubectl apply -f "$SCRIPT_DIR/yamls/application-pod-1.yaml"
kubectl apply -f "$SCRIPT_DIR/yamls/application-pod-2.yaml"