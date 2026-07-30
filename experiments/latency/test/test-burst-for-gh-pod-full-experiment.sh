#!/bin/bash

# Full experiment script: Runs multiple burst sizes with multiple iterations each
# This script loops over different burst sizes and runs multiple iterations for each size

# Configuration
BURST_SIZES=(50 100 200)  # Array of different pod burst sizes to test
ITERATIONS=5                # Number of iterations to run for each burst size

echo "======================================================================="
echo "Starting full experiment with burst sizes: ${BURST_SIZES[@]}"
echo "Running $ITERATIONS iterations for each burst size"
echo "======================================================================="

# Loop over each burst size
for BURST_SIZE in "${BURST_SIZES[@]}"; do
    echo ""
    echo "======================================================================="
    echo "Testing burst size: $BURST_SIZE pods"
    echo "======================================================================="
    
    # Run the iterations script for this burst size
    ./test/test-burst-for-gh-pod-iterations.sh "$BURST_SIZE" "$ITERATIONS"
    
    # Wait between different burst sizes
    echo "Completed burst size $BURST_SIZE. Waiting 60 seconds before next burst size..."
    sleep 60
done

echo ""
echo "======================================================================="
echo "FULL EXPERIMENT COMPLETED!"
echo "======================================================================="
echo "Tested burst sizes: ${BURST_SIZES[@]}"
echo "Iterations per burst size: $ITERATIONS"
echo "Total experiments run: $((${#BURST_SIZES[@]} * ITERATIONS))"
echo ""
echo "Results can be found in:"
for BURST_SIZE in "${BURST_SIZES[@]}"; do
    echo "  - /home/ubuntu/master-thesis-quinten-lauwaert/experiments/latency/results/event-latency-times/burst-$BURST_SIZE/"
done
