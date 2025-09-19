#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECURITY_EVAL_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Step 1: Clean up security group configuration.
"$SECURITY_EVAL_DIR/setup/example-app/tear-down-static-app-sgs.sh"

# Step 2: Clean up application.
"$SECURITY_EVAL_DIR/setup/example-app/tear-down-application.sh"



