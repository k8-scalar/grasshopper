#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECURITY_EVAL_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Step 1: Setup application pods and policy in cluster.
echo "Setting up application pods and policy"
"$SECURITY_EVAL_DIR/setup/example-app/setup-application.sh"

# Step 2: Setup Grasshopper.
echo "Setting up Grasshopper."
kubectl apply -f /home/ubuntu/master-thesis-quinten-lauwaert/grasshopper-operator/Deployment/pods/gh-v2-default-watching.yaml

echo "Waiting for Grasshopper pod to be ready..."
kubectl wait --for=condition=Ready pod/grasshopper-pod --timeout=300s

# Start logging Grasshopper pod output in the background
kubectl logs -f grasshopper-pod > "$SCRIPT_DIR/logs/grasshopper-setup.log" 2>&1 &
LOG_PID=$!

echo "Sleeping for 20 seconds, to let gh process events."
sleep 40

# Step 4: Cleanup - Terminate logging
echo "Terminating log collection..."
if kill -0 $LOG_PID 2>/dev/null; then
    kill $LOG_PID
    echo "Log collection process (PID: $LOG_PID) terminated."
else
    echo "Log collection process was not running or already terminated."
fi


