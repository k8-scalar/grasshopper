
NAMESPACE=test-thesis

# Check if the required arguments are provided
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <num-pods> <interval> <iterations>"
    exit 1
fi

# Burst test parameters from arguments
NUM_PODS=$1
INTERVAL=$2
ITERATIONS=$3 # Number of iterations to run (now from argument)
SLEEP_TIME=10 # time to sleep between iterations

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
    ./test/test-burst.sh "$NUM_PODS" "$INTERVAL" "$i"
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





