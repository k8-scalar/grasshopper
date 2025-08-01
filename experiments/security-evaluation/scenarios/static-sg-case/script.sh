
#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECURITY_EVAL_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Step 1: Setup application security groups.
"$SECURITY_EVAL_DIR/setup/example-app/setup-static-app-sgs.sh"

# Step 2: Setup application pods and policy in cluster.
"$SECURITY_EVAL_DIR/setup/example-app/setup-application.sh"

# Step 3: Perform reverse shell attack (succesfully)
"$SECURITY_EVAL_DIR/reverse_shell/reverse_shell_attack.sh"