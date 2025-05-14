
source ~/kube_venv/bin/activate

NAMESPACE=test-thesis

# Burst test parameters.
SLEEP_TIME=5 # time to sleep between iterations

NUM_PODS=$1
ITERATIONS=$2 # Number of iterations to run.


GH_OUTPUT_FILE_LOCATION="/mnt/nfs_share/latency_results/latency_results.csv"

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

# Iterations loop.
# start_iteration=4
# ITERATIONS=$((start_iteration + ITERATIONS))
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


echo "ITERATION TEST DONE: Did $ITERATIONS iterations with burst of $NUM_PODS pods."





