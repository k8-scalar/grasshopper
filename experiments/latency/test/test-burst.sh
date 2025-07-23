
# Test script: Sets up the cluster, calls the cluster simulator
#              in order to simulate a burst of pods being created. Grasshopper will
#              detect event and handle times and write to output file latency_results/latency_results.csv
#  Params:
#    - NUMPODS:    1  - Number of pods to burst.
#    - ITERATION : 2  - Iteration of the experiment.


# Function to clean up background processes
cleanup() {
    echo "------------------ Cleaning up the cluster. -----------------"

    echo "TEST: Removing network policies and pods created ... "
    # ./scripts/reset_cluster.sh 

    echo "------------------ Cluster cleanup done. --------------------"
}
# Trap script termination (e.g., CTRL+C or exit) and call cleanup
trap cleanup EXIT



# =========================== CONSTANTS ======================================
NAMESPACE=test-thesis

GH_OUTPUT_FILE_LOCATION="/mnt/nfs_share/latency_results/latency_results.csv"
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

echo "Experiment: Creating a burst of $NUM_PODS pods in namespace $NAMESPACE."

# =========================== CLUSTER SETUP ======================================

# Clearing output file.
echo "Clearing output file..."
> $GH_OUTPUT_FILE_LOCATION

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