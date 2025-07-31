#!/bin/bash

# This script creates an example application security group (app-sg) for OpenStack
# that allows ingress and egress traffic on port 8080, and attaches it to 2 nodes.
#
# Prerequisites:
# - OpenStack CLI tools installed and configured
# - Proper authentication credentials set up
# - Worker nodes available in the cluster
#
# Usage:
#     chmod +x setup-static-app-sgs.sh
#     ./setup-static-app-sgs.sh [node1] [node2] [node3]
#
# If no node names are provided, defaults to worker-1, worker-2, and worker

# Exit the script on any error
set -e

# Configuration
SG_NAME="example-app-sg"
SG_DESCRIPTION="Security group for example application allowing port 8080 traffic"
APP_PORT=8080

# Default node names if not provided as arguments
DEFAULT_NODE1="worker-1"
DEFAULT_NODE2="worker-2"
DEFAULT_NODE3="worker"

# Use provided node names or defaults
NODE1=${1:-$DEFAULT_NODE1}
NODE2=${2:-$DEFAULT_NODE2}
NODE3=${3:-$DEFAULT_NODE3}

# Optionally: activate your virtual environment, in order to get access to Openstack CLI tools.
source ~/venv/bin/activate


echo "=== Setting up application security group for OpenStack nodes ==="
echo "Security Group: $SG_NAME"
echo "Target Nodes: $NODE1, $NODE2, $NODE3"
echo "Application Port: $APP_PORT"
echo ""

# Function to check if OpenStack CLI is available
check_openstack_cli() {
    if ! command -v openstack &> /dev/null; then
        echo "Error: OpenStack CLI not found. Please install python-openstackclient."
        exit 1
    fi
}

# Function to check if security group already exists
check_sg_exists() {
    local sg_name=$1
    if openstack security group show "$sg_name" &> /dev/null; then
        return 0  # exists
    else
        return 1  # doesn't exist
    fi
}

# Function to create security group
create_security_group() {
    echo "Creating security group: $SG_NAME"
    openstack security group create \
        --description "$SG_DESCRIPTION" \
        "$SG_NAME"
    
    echo "✓ Security group '$SG_NAME' created successfully"
}

# Function to delete default security group rules
delete_default_rules() {
    echo "Deleting default security group rules..."
    
    # Get all rule IDs for this security group
    local rule_ids=$(openstack security group rule list "$SG_NAME" -f value -c ID)
    
    if [ -n "$rule_ids" ]; then
        echo "  Found default rules to delete:"
        while read -r rule_id; do
            if [ -n "$rule_id" ]; then
                echo "    Deleting rule: $rule_id"
                openstack security group rule delete "$rule_id"
            fi
        done <<< "$rule_ids"
        echo "✓ Default security group rules deleted"
    else
        echo "  No default rules found to delete"
    fi
}

# Function to add security group rules
add_security_rules() {
    echo "Adding security group rules for port $APP_PORT..."
    
    # Allow ingress traffic on port 8080 (TCP) from same security group
    echo "  Adding ingress rule for TCP port $APP_PORT (from same security group)"
    openstack security group rule create \
        --protocol tcp \
        --dst-port $APP_PORT \
        --remote-group "$SG_NAME" \
        --ingress \
        "$SG_NAME" &> /dev/null
    
    # Allow egress traffic on port 8080 (TCP) to same security group
    echo "  Adding egress rule for TCP port $APP_PORT (to same security group)"
    openstack security group rule create \
        --protocol tcp \
        --dst-port $APP_PORT \
        --remote-group "$SG_NAME" \
        --egress \
        "$SG_NAME" &> /dev/null
    
    # Allow ingress traffic on port 8080 (UDP) from same security group - in case app uses UDP
    echo "  Adding ingress rule for UDP port $APP_PORT (from same security group)"
    openstack security group rule create \
        --protocol udp \
        --dst-port $APP_PORT \
        --remote-group "$SG_NAME" \
        --ingress \
        "$SG_NAME" &> /dev/null
    
    # Allow egress traffic on port 8080 (UDP) to same security group
    echo "  Adding egress rule for UDP port $APP_PORT (to same security group)"
    openstack security group rule create \
        --protocol udp \
        --dst-port $APP_PORT \
        --remote-group "$SG_NAME" \
        --egress \
        "$SG_NAME" &> /dev/null
    
    echo "✓ Security group rules added successfully"
}

# Function to attach security group to a node
attach_sg_to_node() {
    local node_name=$1
    echo "Attaching security group '$SG_NAME' to node '$node_name'"
    
    # Check if the server exists
    if ! openstack server show "$node_name" &> /dev/null; then
        echo "Warning: Server '$node_name' not found. Skipping..."
        return 1
    fi
    
    # Add security group to server
    openstack server add security group "$node_name" "$SG_NAME"
    echo "✓ Security group attached to '$node_name'"
}

# Function to display security group rules
show_security_group_rules() {
    echo ""
    echo "=== Security Group Rules for '$SG_NAME' ==="
    openstack security group rule list "$SG_NAME" --format table
    echo ""
}


# Main execution
main() {
    echo "Starting security group setup..."
    
    # Check prerequisites
    check_openstack_cli
    
    # Create security group if it doesn't exist
    if check_sg_exists "$SG_NAME"; then
        echo "Security group '$SG_NAME' already exists. Exiting."
        exit 0
    else
        create_security_group
        delete_default_rules
        add_security_rules
    fi
    
    echo ""
    echo "Attaching security group to nodes..."
    
    # Attach security group to nodes
    attach_sg_to_node "$NODE1"
    attach_sg_to_node "$NODE2"
    attach_sg_to_node "$NODE3"
    
    # Show the security group rules
    show_security_group_rules
    
    echo ""
    echo "=== Setup completed successfully ==="
    echo "Security group '$SG_NAME' has been created and attached to:"
    echo "  - $NODE1"
    echo "  - $NODE2"
    echo "  - $NODE3"
    echo ""
    echo "The security group allows traffic on port $APP_PORT (both TCP and UDP)"
    echo "You can now test connectivity on port $APP_PORT between these nodes."
}

# Show usage information
show_usage() {
    echo "Usage: $0 [node1] [node2] [node3]"
    echo ""
    echo "Creates a security group allowing port 8080 traffic and attaches it to specified nodes."
    echo ""
    echo "Arguments:"
    echo "  node1    First OpenStack server/node name (default: worker-1)"
    echo "  node2    Second OpenStack server/node name (default: worker-2)"
    echo "  node3    Third OpenStack server/node name (default: worker)"
    echo ""
}

# Handle help flag
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_usage
    exit 0
fi

# Run main function
main
