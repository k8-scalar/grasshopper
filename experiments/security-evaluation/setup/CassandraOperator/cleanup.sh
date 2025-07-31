#!/bin/bash

# Cleanup script for Cassandra Operator
set -e

echo "Cleaning up Cassandra Operator..."

# Delete the pod
echo "Deleting pod..."
kubectl delete -f yamls/cassandra-operator-pod.yaml --ignore-not-found=true

# Delete RBAC resources
echo "Deleting RBAC resources..."
kubectl delete -f yamls/role_binding.yaml --ignore-not-found=true
kubectl delete -f yamls/role.yaml --ignore-not-found=true
kubectl delete -f yamls/service_account.yaml --ignore-not-found=true

# Optionally delete namespace
read -p "Delete namespace 'cass-operator'? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Deleting namespace..."
    kubectl delete namespace cass-operator --ignore-not-found=true
fi

echo "Cleanup complete!"
