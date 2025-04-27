
# Test script: Sets up the cluster, the measurer and calls the cluster simulator
#              in order to simulate a burst of pods being created. The measurer will measure
#              CPU-usage and memory-usage and write the results to the results/ directory.
#  Params:
#    - NUMPODS:   1  - Number of pods to burst.
#    - INTERVAL : 2  - Interval in which the measurer will write measurements.


# Function to clean up background processes
cleanup() {
    echo "------------------ Cleaning up the cluster. -----------------"
    # Killing all background processes created (measurer and simulator)
    # echo "Cleaning up all created background processes."
    # kill $(jobs -p) 2>/dev/null

    echo "Killing the measurer process."
    kill $MEASURER_PID

    # echo "Killing the simulator process."
    # kill $SIMULATOR_PID

    echo "TEST: Removing network policies and pods created ... "
    ./scripts/reset_cluster.sh 

    echo "------------------ Cluster cleanup done. --------------------"
}
# Trap script termination (e.g., CTRL+C or exit) and call cleanup
trap cleanup EXIT



# =========================== CONSTANTS ======================================
NAMESPACE=test-thesis

# =========================== ARGUMENTS ======================================

# Check if the required arguments are provided
if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <num-pods> <interval>"
    exit 1
fi

# Reading arguments.
NUM_PODS=$1 # Number of pods to burst.
INTERVAL=$2 # Interval in which the measurer will write measurements.
REST_TIME=30

echo "Experiment: Creating a burst of $NUM_PODS pods in namespace $NAMESPACE."

# =========================== CLUSTER SETUP ======================================

# 1) Setting up the cluster.
# 1.1) Checking if the Cluster is clean.


# 1.2) Applying network policies.
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


# =========================== MEASURER SETUP =====================================

# 2) Setting up the measurer (to measure CPU- and mem-usage) and write to file.
echo "----------- Running the Measurer as a background process ---------------"
python3 measurer/measure_system_performance.py --interval $INTERVAL --num-pods-burst $NUM_PODS > measurer.log 2>&1 &
MEASURER_PID=$!  # Store the PID of the measurer process
echo "Measurer started with PID $MEASURER_PID."



# =========================== CLUSTER SIMULATOR SETUP ===============================

# 3) Running the cluster simulator.
echo "----------- Running the Cluster Simulator as a background process ----------"
python3 simulator/cluster_simulator.py --namespace $NAMESPACE --num-pods $NUM_PODS 2>&1 &
SIMULATOR_PID=$!  # Store the PID of the measurer process
echo "Simulator started with PID $SIMULATOR_PID."
echo "TEST: Burst of X amount of pods created."


# Issue with measurer, when using this code.
# # Wait for the simulator to complete its task
# echo "Waiting for the cluster simulator to finish..."
# wait $SIMULATOR_PID
# echo "Cluster simulator has finished. Proceeding to cleanup."


# Just letting it sleep, to give the simulator time to finish burst.
echo "Sleeping for $REST_TIME, in order to give simulator time to finish burst."
sleep $REST_TIME