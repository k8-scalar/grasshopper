#!/bin/bash

# Simple Recovery Time Experiment Runner

# Configuration
POD_COUNTS=(50 100)  # Array of pod counts to test
ITERATIONS=5                # Number of iterations per pod count

echo "Starting recovery time experiments..."
echo "Pod counts: ${POD_COUNTS[*]}"
echo "Iterations per test: $ITERATIONS"
echo

# Run experiments
for num_pods in "${POD_COUNTS[@]}"; do
    echo "=========================================="
    echo "Running experiment: $num_pods pods, $ITERATIONS iterations"
    echo "=========================================="
    
    ./test-recovery-times.sh "$num_pods" "$ITERATIONS"
    
    if [ $? -eq 0 ]; then
        echo "✅ Completed: $num_pods pods"
    else
        echo "❌ Failed: $num_pods pods"
    fi
    
    echo "Waiting 30 seconds before next experiment..."
    sleep 30
done

echo "All experiments completed!"
