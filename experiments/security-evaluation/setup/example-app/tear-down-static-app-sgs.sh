#!/bin/bash

# This script detaches and deletes the example application security group from OpenStack
# It will find all servers that have the security group attached and remove it before deletion.
#
# Prerequisites:
# - OpenStack CLI tools installed and configured
# - Proper authentication credentials set up
#
# Usage:
#     chmod +x cleanup-static-app-sgs.sh
#     ./cleanup-static-app-sgs.sh [security-group-name]
#
# If no security group name is provided, defaults to "example-app-sg"

# Exit the script on any error
set -e

# Configuration
DEFAULT_SG_NAME="example-app-sg"

# Use provided security group name or default
SG_NAME=${1:-$DEFAULT_SG_NAME}

# Optionally: activate your virtual environment, in order to get access to Openstack CLI tools.
source ~/venv/bin/activate

echo "=== Cleaning up application security group from OpenStack ==="
echo "Security Group: $SG_NAME"
echo ""

# Function to check if OpenStack CLI is available
check_openstack_cli() {
    if ! command -v openstack &> /dev/null; then
        echo "Error: OpenStack CLI not found. Please install python-openstackclient."
        exit 1
    fi
}

# Function to check if security group exists
check_sg_exists() {
    local sg_name=$1
    if openstack security group show "$sg_name" &> /dev/null; then
        return 0  # exists
    else
        return 1  # doesn't exist
    fi
}

# Function to find all servers with the security group attached
find_attached_servers() {
    local sg_name=$1
    echo "Finding servers with security group '$sg_name' attached..." >&2
    
    # Get all servers and check which ones have this security group
    local attached_servers=()
    
    # List all servers and check their security groups
    while IFS= read -r server_name; do
        if [ -n "$server_name" ]; then
            # Check if this server has our security group
            if openstack server show "$server_name" -f value -c security_groups | grep -q "$sg_name"; then
                attached_servers+=("$server_name")
                echo "  Found: $server_name" >&2
            fi
        fi
    done < <(openstack server list -f value -c Name)
    
    # Return the list of attached servers
    printf '%s\n' "${attached_servers[@]}"
}

# Function to detach security group from a server
detach_sg_from_server() {
    local server_name=$1
    local sg_name=$2
    
    echo "Detaching security group '$sg_name' from server '$server_name'"
    
    # Remove security group from server
    if openstack server remove security group "$server_name" "$sg_name" 2>/dev/null; then
        echo "✓ Security group detached from '$server_name'"
        return 0
    else
        echo "✗ Failed to detach security group from '$server_name'"
        return 1
    fi
}

# Function to delete security group
delete_security_group() {
    local sg_name=$1
    
    echo "Deleting security group '$sg_name'..."
    
    if openstack security group delete "$sg_name" 2>/dev/null; then
        echo "✓ Security group '$sg_name' deleted successfully"
        return 0
    else
        echo "✗ Failed to delete security group '$sg_name'"
        return 1
    fi
}

# Main cleanup function
main() {
    echo "Starting security group cleanup..."
    
    # Check prerequisites
    check_openstack_cli
    
    # Check if security group exists
    if ! check_sg_exists "$SG_NAME"; then
        echo "Security group '$SG_NAME' does not exist. Nothing to clean up."
        exit 0
    fi
    
    # Find all attached servers
    echo "Scanning for attached servers..."
    attached_servers=($(find_attached_servers "$SG_NAME"))
    
    if [ ${#attached_servers[@]} -eq 0 ]; then
        echo "No servers found with security group '$SG_NAME' attached."
    else
        echo "Found ${#attached_servers[@]} server(s) with security group attached:"
        printf '  - %s\n' "${attached_servers[@]}"
        echo ""
        
        # Detach from all servers
        echo "Detaching security group from all servers..."
        
        for server in "${attached_servers[@]}"; do
            detach_sg_from_server "$server" "$SG_NAME"
        done
    fi
    
    echo ""
    echo "Proceeding with security group deletion..."
    
    # Delete the security group
    if delete_security_group "$SG_NAME"; then
        echo ""
        echo "=== Cleanup completed successfully ==="
        echo "Security group '$SG_NAME' has been removed from all servers and deleted."
    else
        echo ""
        echo "=== Cleanup failed ==="
        echo "Could not delete security group '$SG_NAME'."
        echo "Please check for remaining attachments or dependencies."
        exit 1
    fi
}

# Show usage information
show_usage() {
    echo "Usage: $0 [security-group-name]"
    echo ""
    echo "Detaches and deletes the specified security group from all OpenStack servers."
    echo ""
    echo "Arguments:"
    echo "  security-group-name    Name of the security group to clean up (default: example-app-sg)"
    echo ""
}

# Handle help flag
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_usage
    exit 0
fi

# Run main function
main
