
# Test script: Sets up the cluster, the measurer and calls the cluster simulator
#              in order to simulate a burst of pods being created. The measurer will measure
#              CPU-usage and memory-usage and write the results to the results/ directory.



# Function to clean up background processes
cleanup() {
    echo "------------------ Cleaning up the cluster. -----------------"
    echo "TEST: Resetting cluster."
    ./scripts/reset_cluster.sh 

    # Killing all background processes created (aka grasshopper, measurer, ...)
    echo "Cleaning up all created background processes."
    kill $(jobs -p) 2>/dev/null
    echo "------------------ Cluster cleanup done. --------------------"
}

# Trap script termination (e.g., CTRL+C or exit) and call cleanup
trap cleanup EXIT


# =========================== ARGUMENTS ======================================

# # Check if the required arguments are provided
# if [ "$#" -lt 2 ]; then
#     echo "Usage: $0 <namespace> <num-pods>"
#     exit 1
# fi

# Read arguments
NAMESPACE=test-thesis
NUM_PODS=10

echo "Experiment: Creating a burst of $NUM_PODS pods in namespace $NAMESPACE."

# =========================== CLUSTER SETUP ======================================

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


# =========================== MEASURER SETUP =====================================

# 2) Setting up the measurer (to measure CPU- and mem-usage) and write to file.
echo "----------- Running the Measurer as a background process ---------------"
python3 measurer/measure_system_performance.py --interval 1 > measurer.log 2>&1 &



# # 3) Setting up grasshopper
# echo "----------- Running GrassHopper as a background process ----------"
# # ensuring the virtual environment is activated.
# source ~/grasshopper-operator/kube_venv/bin/activate
# echo "Environment variables:" >> debug.log
# env >> debug.log
# python3 ../../grasshopper/grasshopper-code/code/main.py --mode PLS --namespace thesis-test > grasshopper.log 2>&1 &


# =========================== CLUSTER SIMULATOR SETUP ===============================

# 4) Running the cluster simulator.
echo "----------- Running the Cluster Simulator as a background process ----------"
python3 simulator/cluster_simulator.py --namespace $NAMESPACE --num-pods $NUM_PODS &

echo "Sleeping for 60 seconds to let Grasshopper be in peace."
sleep 10

echo "TEST: Burst of X amount of pods created."
# echo "Sleeping for 2 seconds, to ensure everything has finished"
sleep 2



# 5) Cleaning up. Will be done by cleanup()-function when script exits.