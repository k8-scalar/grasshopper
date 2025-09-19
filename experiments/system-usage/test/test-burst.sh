
# Test script: Sets up the cluster, the measurer and calls the cluster simulator
#            # Check if the script ran successfully
if [ $? -eq 0 ]; then
    echo "Successfully applied network policies."
else
    echo "There was a problem with applying the network policies."
fi

echo "----------------------- Cluster setup done. ---------------------------"


# =========================== MEASURER SETUP ====================================="o simulate a burst of pods being created. The measurer will measure
#              CPU-usage and memory-usage and write the results to the results/ directory.
#  Params:
#    - NUMPODS:   1  - Number of pods to burst.
#    - INTERVAL : 2  - Interval in which the measurer will write measurements.
#    - ITERATION: 3  - Iteration number of the experiment.


cleanup() {
    echo "------------------ Cleaning up the cluster. -----------------"
    # Killing all background processes created (measurer and simulator)
    # echo "Cleaning up all created background processes."
    # kill $(jobs -p) 2>/dev/null

    # Only kill measurer if it's still running (might have been shut down already)
    if [ ! -z "$MEASURER_PID" ] && kill -0 "$MEASURER_PID" 2>/dev/null; then
        echo "Killing the measurer process."
        kill $MEASURER_PID
    fi

    # Kill kubectl logs process if running
    if [ ! -z "$KUBECTL_LOGS_PID" ] && kill -0 "$KUBECTL_LOGS_PID" 2>/dev/null; then
        echo "Stopping kubectl logs process."
        kill $KUBECTL_LOGS_PID
    fi

    # Delete Grasshopper pod if it exists
    echo "Deleting Grasshopper pod..."
    kubectl delete pod grasshopper-pod --namespace=default --ignore-not-found=true
    
    # Wait for pod to be fully deleted
    echo "Waiting for Grasshopper pod to be deleted..."
    kubectl wait --for=delete pod/grasshopper-pod --namespace=default --timeout=60s 2>/dev/null || true
    echo "Grasshopper pod deletion complete."

    # echo "Killing the simulator process."
    # kill $SIMULATOR_PID

    echo "TEST: Removing network policies and pods created ... "
    ./scripts/reset_cluster.sh 

    echo "Removing security groups..."
    python3 "/home/ubuntu/master-thesis-quinten-lauwaert/grasshopper-operator/grasshopper-pod/code/openstackfiles/remove_excess_sgs.py"

    echo "------------------ Cluster cleanup done. --------------------"
}
# Trap script termination (e.g., CTRL+C or exit) and call cleanup
trap cleanup EXIT


# =========================== CONSTANTS ======================================
NAMESPACE=test-thesis
GH_POD_YAML="/home/ubuntu/master-thesis-quinten-lauwaert/grasshopper-operator/Deployment/pods/gh-v2.yaml"

# =========================== ARGUMENTS ======================================

# Check if the required arguments are provided
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <num-pods> <interval> <iteration>"
    exit 1
fi

# Reading arguments.
NUM_PODS=$1 # Number of pods to burst.
INTERVAL=$2 # Interval in which the measurer will write measurements.
ITERATION=$3 # Iteration number of the experiment.
REST_TIME=30

# Create log file path for Grasshopper
GH_LOG_FILE="/home/ubuntu/master-thesis-quinten-lauwaert/experiments/system-usage/results/logs/gh_burst_${NUM_PODS}_iteration_${ITERATION}.log"

# Create log directory if not exists
mkdir -p "/home/ubuntu/master-thesis-quinten-lauwaert/experiments/system-usage/results/logs"

echo "Experiment: Creating a burst of $NUM_PODS pods in namespace $NAMESPACE."

# =========================== GRASSHOPPER SETUP =====================================

# Starting Grasshopper pod BEFORE applying policies to ensure clean initialization
echo "----------- Deploying Grasshopper pod ---------------"
kubectl apply -f "$GH_POD_YAML"

# Wait for pod to be ready
echo "Waiting for Grasshopper pod to be ready..."
kubectl wait --for=condition=Ready pod/grasshopper-pod --namespace=default --timeout=120s
if [ $? -eq 0 ]; then
    echo "Grasshopper pod is ready."
    
    # Start logging the pod output to file
    echo "Starting to log Grasshopper pod output to $GH_LOG_FILE"
    kubectl logs -f grasshopper-pod --namespace=default > "$GH_LOG_FILE" 2>&1 &
    KUBECTL_LOGS_PID=$!
    echo "Kubectl logs started with PID $KUBECTL_LOGS_PID."
else
    echo "Warning: Grasshopper pod did not become ready within timeout, continuing anyway..."
fi


# =========================== MEASURER SETUP =====================================

# 2) Setting up the measurer (to measure CPU- and mem-usage) and write to file.
echo "----------- Running the Measurer as a background process ---------------"
python3 measurer/measure_system_performance.py --interval $INTERVAL --num-pods-burst $NUM_PODS --iteration $ITERATION > measurer.log 2>&1 &
MEASURER_PID=$!  # Store the PID of the measurer process
echo "Measurer started with PID $MEASURER_PID."

# =========================== CLUSTER SETUP ======================================

# 3) Setting up the cluster.
# 3.1) Applying network policies AFTER Grasshopper is ready.
echo "----------------------- Setting up Cluster ----------------------------"
echo "3: TEST: Applying network policies..."
./scripts/apply-all-policies.sh test/networkpolicies 
# Check if the script ran successfully
if [ $? -eq 0 ]; then
    echo "Successfully applied network policies."
else
    echo "There was a problem with applying the network policies."
fi
echo "----------------------- Cluster setup done. ---------------------------"


# =========================== CLUSTER SIMULATOR SETUP ===============================

# 4) Running the cluster simulator.
echo "----------- Running the Cluster Simulator as a background process ----------"
python3 simulator/cluster_simulator.py --namespace $NAMESPACE --num-pods $NUM_PODS 2>&1 &
SIMULATOR_PID=$!  # Store the PID of the measurer process
echo "Simulator started with PID $SIMULATOR_PID."
echo "TEST: Burst of X amount of pods created."


# Just letting it sleep, to give the simulator time to finish burst.
echo "Sleeping for $REST_TIME, in order to give simulator time to finish burst."
sleep $REST_TIME

# Gracefully shutdown the measurer to save results
echo "Experiment completed. Shutting down measurer to save results..."
if [ ! -z "$MEASURER_PID" ] && kill -0 "$MEASURER_PID" 2>/dev/null; then
    echo "Sending SIGTERM to measurer process (PID: $MEASURER_PID)..."
    kill -TERM "$MEASURER_PID"
    
    # Wait a bit for graceful shutdown
    sleep 2
    
    # Check if it's still running and force kill if necessary
    if kill -0 "$MEASURER_PID" 2>/dev/null; then
        echo "Measurer still running, force killing..."
        kill -KILL "$MEASURER_PID"
    fi
    
    echo "Measurer shutdown complete."
else
    echo "Measurer process not found or already terminated."
fi