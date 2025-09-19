
#!/bin/bash

# Configuration
num_pods_to_burst=( "25" "50" "100")
intervals=("1" "1" "1") 
iterations=5  # Number of iterations to run for each experiment

# Get the absolute path of the script directory and parent directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Running full burst experiment from: $PARENT_DIR"

# Change to the parent directory so relative paths in nested scripts work correctly
cd "$PARENT_DIR"

# Loop through both lists using an index
for i in "${!num_pods_to_burst[@]}"; do
    num_pods="${num_pods_to_burst[$i]}"
    interval="${intervals[$i]}"
    
    echo "========================================================"
    echo "Experiment $((i+1))/${#num_pods_to_burst[@]}: $num_pods pods, interval: ${interval}s, iterations: $iterations"
    echo "========================================================"
    
    ./test/test-burst-iterations.sh "$num_pods" "$interval" "$iterations"
    
    echo "Experiment $((i+1)) completed successfully."
    echo ""
done

echo "All experiments completed successfully!"