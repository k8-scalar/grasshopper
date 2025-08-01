#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECURITY_EVAL_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Step 1: Setting up static security group configuration.
echo "Setting up static security group configuration."
"$SECURITY_EVAL_DIR/setup/example-app/setup-static-app-sgs.sh"

# Step 2: Setup application pods and policy in cluster.
echo "Setting up application pods and policy"
"$SECURITY_EVAL_DIR/setup/example-app/setup-application.sh"

# Step 3: Perform reverse shell attack

    # Go to your machine, where the cass-operator pod is running,
    # and run the reverse_shell/reverse_shell_attack.sh script.


