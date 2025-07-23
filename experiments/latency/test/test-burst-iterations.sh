NAMESPACE=test-thesis

# Burst test parameters.
SLEEP_TIME=5 # time to sleep between iterations

NUM_PODS=$1
ITERATIONS=$2 # Number of iterations to run.

GH_OUTPUT_FILE_LOCATION="/mnt/nfs_share/latency_results/latency_results.csv"
GH_LOG_FILE="/home/ubuntu/master-thesis-quinten-lauwaert/experiments/latency/results/logs/gh_og_burst_${NUM_PODS}_iters_${ITERATIONS}.log"
GH_LOCATION="/home/ubuntu/master-thesis-quinten-lauwaert/grasshopper/grasshopper-code/code/main_with_timing.py"

# Create log folder if not exists.
mkdir -p "/home/ubuntu/master-thesis-quinten-lauwaert/experiments/latency/results/logs"

# Create output directory if not exists.
TARGET_DIR="/home/ubuntu/master-thesis-quinten-lauwaert/experiments/latency/results/event-latency-times/burst-$NUM_PODS"
mkdir -p "$TARGET_DIR"

check_if_cluster_is_clean(){
    # Check for pods
    pods=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)

    # Check for network policies
    policies=$(kubectl get networkpolicy -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)

    if [[ "$pods" -eq 0 && "$policies" -eq 0 ]]; then
        echo "Cluster is clean!"
    else
        echo "Cluster is not fully clean."
        exit 1
    fi
}

# Start grasshopper.py in background and log output
echo "Starting grasshopper.py..."
python3 $GH_LOCATION --mode PLS > "$GH_LOG_FILE" 2>&1 &
GH_PID=$!
echo "Grasshopper started with PID $GH_PID"

# Iterations loop.
for ((i=1; i<=ITERATIONS; i++)) do
    echo "Starting iteration $i"
    ./test/test-burst.sh "$NUM_PODS" "$i"
    echo "Iteration $i done. "

    # Grasshopper has now written test-results to output-file, so copying this file to proper location.
    echo "Copying results to output file"
    TARGET_FILE_LOCATION="$TARGET_DIR/iteration-$i.csv"
    cp "$GH_OUTPUT_FILE_LOCATION" "$TARGET_FILE_LOCATION"

    echo "Clearing output file..."
    > $GH_OUTPUT_FILE_LOCATION

    # Resetting cluster.
    ./scripts/reset_cluster.sh

    # Cleanliness check.
    # echo "Cleanliness check."
    # check_if_cluster_is_clean
    # echo "Check done!"

    echo "Sleeping for $SLEEP_TIME seconds before starting the next iteration."
    sleep $SLEEP_TIME    
done

# Stop grasshopper.py
echo "Stopping grasshopper.py with PID $GH_PID"
kill "$GH_PID"
wait "$GH_PID" 2>/dev/null


echo "ITERATION TEST DONE: Did $ITERATIONS iterations with burst of $NUM_PODS pods."





