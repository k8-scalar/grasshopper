#!/bin/bash

# Test script: Starts the Grasshopper operator pod, waits for it to be ready,
#              sets up the cluster, calls the cluster simulator to simulate 
#              a burst of pods being created, copies results, and cleans up.
#  Params:
#    - NUMPODS:    1  - Number of pods to burst.
#    - ITERATION : 2  - Iteration of the experiment.

# Function to clean up background processes
cleanup() {
    echo "------------------ Cleaning up the cluster and pods. -----------------"

    echo "TEST: Stopping log collection..."
    if [ ! -z "$LOG_PID" ]; then
        kill $LOG_PID 2>/dev/null || true
        echo "Log collection stopped."
    fi

    echo "TEST: Deleting Grasshopper pod..."
    kubectl delete pod grasshopper-pod-latency --ignore-not-found

    echo "TEST: Removing network policies and pods created ... "
    ./scripts/reset_cluster_all.sh > /dev/null 

    python3 /home/ubuntu/master-thesis-quinten-lauwaert/grasshopper-operator/grasshopper-pod/code/openstackfiles/remove_excess_sgs.py

    echo "------------------ Cleanup done. --------------------"
}
# Trap script termination (e.g., CTRL+C or exit) and call cleanup
trap cleanup EXIT

# =========================== CONSTANTS ======================================
NAMESPACE=test-thesis
GH_OUTPUT_FILE_LOCATION="/mnt/nfs_share/latency_results/latency_results.csv"
GH_POD_YAML="/home/ubuntu/master-thesis-quinten-lauwaert/grasshopper-operator/Deployment/pods/gh-v3-latency.yaml"
# =========================== ARGUMENTS ======================================

# Check if the required arguments are provided
if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <num-pods> <iteration>"
    exit 1
fi

# Reading arguments.
NUM_PODS=$1 # Number of pods to burst.
ITERATION=$2 # Interval in which the measurer will write measurements.
REST_TIME=40

# Create output directory if not exists.
TARGET_DIR="/home/ubuntu/master-thesis-quinten-lauwaert/experiments/latency/results/event-latency-times/burst-$NUM_PODS"
mkdir -p "$TARGET_DIR"

# Create logs directory and log file for Grasshopper pod output
LOGS_DIR="/home/ubuntu/master-thesis-quinten-lauwaert/experiments/latency/results/logs/burst-$NUM_PODS"
mkdir -p "$LOGS_DIR"
GH_LOG_FILE="$LOGS_DIR/gh_pod_log_iter_${ITERATION}.log"

echo "Experiment: Creating a burst of $NUM_PODS pods in namespace $NAMESPACE with Grasshopper operator."

# =========================== GRASSHOPPER STARTUP ======================================

echo "----------------------- Starting Grasshopper Pod ----------------------------"

# 1) Delete any existing Grasshopper pod
echo "1: Deleting any existing Grasshopper pod..."
kubectl delete pod grasshopper-pod-latency --ignore-not-found

# 2) Start the Grasshopper pod
echo "2: Starting Grasshopper pod..."
kubectl apply -f $GH_POD_YAML

# 3) Wait for the pod to be ready
echo "3: Waiting for Grasshopper pod to be ready..."
kubectl wait --for=condition=Ready pod/grasshopper-pod-latency --timeout=600s

if [ $? -eq 0 ]; then
    echo "Grasshopper pod is ready!"
else
    echo "ERROR: Grasshopper pod failed to become ready within timeout."
    exit 1
fi

# 4) Give Grasshopper a moment to initialize
echo "4: Giving Grasshopper 5 seconds to initialize..."
sleep 5

# 5) Start collecting Grasshopper pod logs in background
echo "5: Starting log collection for Grasshopper pod..."
kubectl logs -f grasshopper-pod-latency > "$GH_LOG_FILE" 2>&1 &
LOG_PID=$!
echo "Log collection started with PID $LOG_PID, saving to $GH_LOG_FILE"

echo "----------------------- Grasshopper startup done. ---------------------------"

# =========================== CLUSTER SETUP ======================================

# Clearing output file.
echo "Clearing output file..."
> $GH_OUTPUT_FILE_LOCATION

# 1) Setting up the cluster.
# 1.1) Applying network policies.
echo "----------------------- Setting up Cluster ----------------------------"
echo "1: TEST: Applying network policies..."
./scripts/apply-all-policies.sh test/networkpolicies/

# Check if the script ran successfully
if [ $? -eq 0 ]; then
    echo "Successfully applied network policies."
else
    echo "There was a problem with applying the network policies."
fi
echo "----------------------- Cluster setup done. ---------------------------"

# =========================== CLUSTER SIMULATOR SETUP ===============================

# 2) Running the cluster simulator.
echo "----------- Running the Cluster Simulator as a background process ----------"
python3 simulator/cluster_simulator.py --namespace $NAMESPACE --num-pods $NUM_PODS --iteration $ITERATION 2>&1 &
SIMULATOR_PID=$!  # Store the PID of the simulator process
echo "Simulator started with PID $SIMULATOR_PID."
echo "TEST: Burst of $NUM_PODS pods created."

# Sleeping, in order to give the simulator time to do it's bursts.
echo "Sleeping for $REST_TIME seconds, in order to give simulator time to finish burst."
sleep $REST_TIME

# =========================== RESULTS COLLECTION ===============================

echo "----------------------- Collecting Results ----------------------------"

# Wait for any remaining processing
echo "Waiting additional 10 seconds for result processing..."
sleep 10

# Stop log collection to ensure all logs are captured
echo "Stopping log collection to finalize logs..."
if [ ! -z "$LOG_PID" ]; then
    kill $LOG_PID 2>/dev/null || true
    sleep 2  # Give a moment for the log file to be written
fi

# Check if results file exists and copy it
if [ -f "$GH_OUTPUT_FILE_LOCATION" ]; then
    TARGET_FILE_LOCATION="$TARGET_DIR/iteration-$ITERATION.csv"
    
    echo "Copying results from $GH_OUTPUT_FILE_LOCATION to $TARGET_FILE_LOCATION"
    cp "$GH_OUTPUT_FILE_LOCATION" "$TARGET_FILE_LOCATION"
    
    echo "Results saved to: $TARGET_FILE_LOCATION"

    echo "Clearing output file..."
    > $GH_OUTPUT_FILE_LOCATION
else
    echo "WARNING: Results file $GH_OUTPUT_FILE_LOCATION not found!"
fi

echo "----------------------- Results collection done. ----------------------"

echo "Experiment completed successfully!"
