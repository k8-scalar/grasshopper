#!/bin/bash

# Script to check OpenStack security group SG-app:example-app and its attachments
# Author: Generated for security evaluation logging
# Date: $(date)

echo "=========================================="
echo "Security Group Analysis: SG-app:example-app"
echo "Timestamp: $(date)"
echo "=========================================="
echo

# Find the security group ID
echo "1. Finding SG-app:example-app security group..."
SG_ID=$(openstack security group list -f value -c ID -c Name | grep "SG-app:example-app" | awk '{print $1}')

if [ -z "$SG_ID" ]; then
    echo "ERROR: Security group SG-app:example-app not found!"
    exit 1
fi

echo "Found security group: SG-app:example-app"
echo "Security Group ID: $SG_ID"
echo

# Show security group details
echo "2. Security Group Details:"
echo "=========================="
openstack security group show $SG_ID
echo

# Show security group rules in a readable format
echo "3. Security Group Rules:"
echo "======================="
openstack security group rule list $SG_ID
echo

# List all servers
echo "4. Available Servers:"
echo "===================="
openstack server list
echo

# Check which servers have this security group attached
echo "5. Servers with SG-app:example-app attached:"
echo "============================================"
found_attachments=false

for server_id in $(openstack server list -f value -c ID); do
    server_name=$(openstack server show $server_id -f value -c name)
    security_groups=$(openstack server show $server_id -f value -c security_groups)
    
    if [[ "$security_groups" == *"SG-app:example-app"* ]]; then
        echo "✓ Server: $server_name (ID: $server_id)"
        echo "  Security Groups: $security_groups"
        found_attachments=true
    fi
done

if [ "$found_attachments" = false ]; then
    echo "No servers found with SG-app:example-app attached"
fi

echo
echo "6. Summary:"
echo "==========="
echo "Security Group: SG-app:example-app"
echo "ID: $SG_ID"
echo "Creation time: $(openstack security group show $SG_ID -f value -c created_at)"
echo "Last updated: $(openstack security group show $SG_ID -f value -c updated_at)"
echo "Revision: $(openstack security group show $SG_ID -f value -c revision_number)"

# Count rules
rule_count=$(openstack security group rule list $SG_ID -f value | wc -l)
echo "Total rules: $rule_count"

# Check for specific port 8080 rules
port_8080_rules=$(openstack security group rule list $SG_ID -f value | grep "8080" | wc -l)
echo "Port 8080 rules: $port_8080_rules"

echo
echo "Analysis completed at: $(date)"
echo "=========================================="
