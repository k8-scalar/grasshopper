#!/bin/bash

# Simple script to loop over test-burst-for-gh-pod.sh multiple times
# Usage: ./test-burst-for-gh-pod-iterations.sh <num-pods> <amount-iterations>

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <num-pods> <amount-iterations>"
    exit 1
fi

NUM_PODS=$1
AMOUNT_ITERATIONS=$2

echo "Running $AMOUNT_ITERATIONS iterations with $NUM_PODS pods each"

for ((i=1; i<=AMOUNT_ITERATIONS; i++)); do
    echo "Starting iteration $i of $AMOUNT_ITERATIONS"
    ./test/test-burst-for-gh-pod.sh "$NUM_PODS" "$i"
    
    # Sleep between iterations (except for the last one)
    if [ "$i" -lt "$AMOUNT_ITERATIONS" ]; then
        echo "Waiting 10 seconds before next iteration..."
        sleep 10
    fi
done

echo "All iterations completed!"
