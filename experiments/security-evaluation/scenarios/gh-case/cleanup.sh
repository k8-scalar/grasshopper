#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECURITY_EVAL_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Step 1: Clean up application.
"$SECURITY_EVAL_DIR/setup/example-app/tear-down-application.sh"

echo "Removing security groups..."
python3 "/home/ubuntu/master-thesis-quinten-lauwaert/grasshopper/grasshopper-code/code/openstackfiles/remove_excess_sgs.py"


