

# Step 1: Setup application security groups.
./../setup/example-app/setup-static-app-sgs.sh

# Step 2: Setup application pods and policy in cluster.
./../setup/example-app/setup-application.sh

# Step 3: Perform reverse shell attack (succesfully)
./../reverse_shell/reverse_shell_attack.sh