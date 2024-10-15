#!/bin/bash

# Set variables for project and security group names
export PROJECT="prj.dnet.u0018104"  # Set your project name here
export SG="default"    # Set your security group name here

# Get the project ID for the given project name
export PROJECT_ID=$(openstack project show -f value -c id $PROJECT)

# Check if the security group exists by name and project
DEFAULT_SEC_GROUP=$(openstack security group list --project $PROJECT_ID -f value -c ID -c Name | grep -w $SG | awk '{print $1}')

# If the security group does not exist, create it
if [ -z "$DEFAULT_SEC_GROUP" ]; then
  echo "Creating security group $SG for project $PROJECT..."
  DEFAULT_SEC_GROUP=$(openstack security group create $SG --description "Security group for project $PROJECT" --project $PROJECT_ID -f value -c id)
else
  echo "Security group $SG already exists with ID: $DEFAULT_SEC_GROUP"
fi



# Add SSH ingress rule (IPv4, port 22, TCP)
echo "Adding SSH ingress rule to security group $SG..."
openstack security group rule create --ethertype IPv4 --protocol tcp --dst-port 22 --ingress --remote-ip 0.0.0.0/0 $DEFAULT_SEC_GROUP

# Add ICMP ingress rule (IPv4)
echo "Adding ICMP ingress rule to security group $SG..."
openstack security group rule create --ethertype IPv4 --protocol icmp --ingress --remote-ip 0.0.0.0/0 $DEFAULT_SEC_GROUP

# Add ingress rule for all IPv6-based protocols from instances with default security group attached
echo "Adding IPv6 ingress rule from security group $SG..."
openstack security group rule create --ethertype IPv6 --ingress --remote-group $SG $DEFAULT_SEC_GROUP

# Add ingress rule for all IPv4-based protocols from instances with default security group attached
echo "Adding IPv4 ingress rule from security group $SG..."
openstack security group rule create --ethertype IPv4 --ingress --remote-group $SG $DEFAULT_SEC_GROUP

# Add egress rule for all IPv4-based protocols to anywhere
echo "Adding egress rule for all IPv4 protocols to anywhere in security group $SG..."
openstack security group rule create --ethertype IPv4 --egress --remote-ip 0.0.0.0/0 $DEFAULT_SEC_GROUP

# Add egress rule for all IPv6-based protocols to anywhere
echo "Adding egress rule for all IPv6 protocols to anywhere in security group $SG..."
openstack security group rule create --ethertype IPv6 --egress --remote-ip ::/0  $DEFAULT_SEC_GROUP

echo "All rules added successfully to security group $SG!"
