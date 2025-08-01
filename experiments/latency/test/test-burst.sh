
# Test script: Sets up the cluster, calls the cluster simulator
#              in order to simulate a burst of pods being created. Grasshopper will
#              detect event and handle times and write to output file latency_results/latency_results.csv
#  Params:
#    - NUMPODS:    1  - Number of pods to burst.
#    - ITERATION : 2  - Iteration of the experiment.

# Check if the required arguments are provided
if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <num-pods> <iteration>"
    exit 1
fi

# Reading arguments.
NUM_PODS=$1 # Number of pods to burst.
ITERATION=$2 # Interval in which the measurer will write measurements.
REST_TIME=60

# Function to clean up background processes
cleanup() {
    echo "------------------ Cleaning up the cluster. -----------------"

    # Kill grasshopper process if it's running
    if [ ! -z "$GH_PID" ] && kill -0 "$GH_PID" 2>/dev/null; then
        echo "Stopping grasshopper process (PID: $GH_PID)..."
        kill "$GH_PID"
        wait "$GH_PID" 2>/dev/null
        echo "Grasshopper process stopped."
    fi

    echo "TEST: Removing network policies and pods created ... "
    ./scripts/reset_cluster.sh 

    echo "Cleaning up creating security groups."
    python3 "/home/ubuntu/master-thesis-quinten-lauwaert/grasshopper/grasshopper-code/code/openstackfiles/remove_excess_sgs.py"

    echo "------------------ Cluster cleanup done. --------------------"
}
# Trap script termination (e.g., CTRL+C or exit) and call cleanup
trap cleanup EXIT

# =========================== CONSTANTS ======================================
NAMESPACE=test-thesis

GH_LOG_FILE="/home/ubuntu/master-thesis-quinten-lauwaert/experiments/latency/results/logs/burst_${NUM_PODS}_iter_${ITERATION}.log"
GH_LOCATION="/home/ubuntu/master-thesis-quinten-lauwaert/grasshopper/grasshopper-code/code/main_with_timing.py"
GH_OUTPUT_FILE_LOCATION="/mnt/nfs_share/latency_results/latency_results.csv"
# =========================== ARGUMENTS ======================================

mkdir -p "/home/ubuntu/master-thesis-quinten-lauwaert/experiments/latency/results/logs"

# Create output directory if not exists.
TARGET_DIR="/home/ubuntu/master-thesis-quinten-lauwaert/experiments/latency/results/event-latency-times/burst-$NUM_PODS"
mkdir -p "$TARGET_DIR"

echo "Experiment: Creating a burst of $NUM_PODS pods in namespace $NAMESPACE."

# =========================== CLUSTER SETUP ======================================

# Clearing output file.
echo "Clearing output file..."
> $GH_OUTPUT_FILE_LOCATION


# Start grasshopper.py in background and log output
echo "Starting grasshopper.py..."
python3 $GH_LOCATION --mode PLS > "$GH_LOG_FILE" 2>&1 &
GH_PID=$!
echo "Grasshopper started with PID $GH_PID"

echo "Sleeping for 5 seconds, to let GH initialize."
sleep 5


# 1) Setting up the cluster.
# 1.1) Applying network policies.
echo "----------------------- Setting up Cluster ----------------------------"
echo "1: TEST: Applying network policies..."
./scripts/apply-all-policies.sh test/networkpolicies 
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
SIMULATOR_PID=$!  # Store the PID of the measurer process
echo "Simulator started with PID $SIMULATOR_PID."
echo "TEST: Burst of X amount of pods created."

# Sleeping, in order to give the simulator time to do it's bursts.
echo "Sleeping for $REST_TIME, in order to give simulator time to finish burst."
sleep $REST_TIME


# Grasshopper has now written test-results to output-file, so copying this file to proper location.
echo "Copying results to output file"
TARGET_FILE_LOCATION="$TARGET_DIR/iteration-$ITERATION.csv"
cp "$GH_OUTPUT_FILE_LOCATION" "$TARGET_FILE_LOCATION"

