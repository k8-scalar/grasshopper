#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECURITY_EVAL_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Step 1: Setup application pods and policy in cluster.
echo "Setting up application pods and policy"
"$SECURITY_EVAL_DIR/setup/example-app/setup-application.sh"

# Step 2: Setup Grasshopper.
echo "Setting up Grasshopper."
python3 -u "/home/ubuntu//master-thesis-quinten-lauwaert/grasshopper/grasshopper-code/code/main.py" --mode PLS --namespace default > logs/gh-case-setup.log 2>&1 &
GH_PID=$!

echo "Giving GH 10 seconds to initialize."
sleep 10

# Step 3: Perform reverse shell attack

    # Go to your machine, where the cass-operator pod is running,
    # and run the reverse_shell/reverse_shell_attack.sh script.


# Step 4: Cleanup - Terminate Grasshopper process
echo "Terminating Grasshopper process..."
if kill -0 $GH_PID 2>/dev/null; then
    kill $GH_PID
    echo "Grasshopper process (PID: $GH_PID) terminated."
else
    echo "Grasshopper process (PID: $GH_PID) was not running or already terminated."
fi


