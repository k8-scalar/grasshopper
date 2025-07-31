#!/bin/bash

# Setup script for Cassandra Operator Pod and RBAC
set -e

echo "Setting up Cassandra Operator..."

# Create namespace
echo "Creating namespace..."
kubectl create namespace cass-operator --dry-run=client -o yaml | kubectl apply -f -

# Apply RBAC resources in order
echo "Applying service account..."
kubectl apply -f yamls/service_account.yaml

echo "Applying roles..."
kubectl apply -f yamls/role.yaml

echo "Applying role bindings..."
kubectl apply -f yamls/role_binding.yaml

# Wait for RBAC to propagate
echo "Waiting for RBAC to propagate..."
sleep 3

# Deploy the pod
echo "Deploying Cassandra operator pod..."
kubectl apply -f yamls/cassandra-operator-pod.yaml

# Wait for pod to be ready
echo "Waiting for pod to be ready..."
kubectl wait --for=condition=Ready pod/dummy-cass-operator -n cass-operator --timeout=60s

echo "Setup complete!"
echo "Pod status:"
kubectl get pod dummy-cass-operator -n cass-operator
