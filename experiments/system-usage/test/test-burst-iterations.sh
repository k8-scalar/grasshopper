
source ~/kube_venv/bin/activate

NAMESPACE=test-thesis

# Burst test parameters.
ITERATIONS=10 # Number of iterations to run.
NUM_PODS=10   # Number of pods to burst in each iteration.
SLEEP_TIME=5 # time to sleep between iterations
INTERVAL=0.2  # Interval in which to take measurements.

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

for ((i=1; i<=ITERATIONS; i++)) do
    echo "Starting iteration $i"
    ./test/test-burst.sh "$NUM_PODS" "$SLEEP_TIME" "$INTERVAL"
    echo "Iteration $i done. "

    echo "Sleeping for 5 seconds to let everything balance out."
    sleep 5

    # Cleanliness check.
    echo "Cleanliness check."
    check_if_cluster_is_clean
    echo "Check done!"

    echo "Sleeping for $SLEEP_TIME seconds before starting the next iteration."
    sleep $SLEEP_TIME    
done


echo "ITERATION TEST DONE: Did $ITERATIONS iterations with burst of $NUM_PODS pods."





