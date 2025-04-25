
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



# 1) Setting up the cluster.
# 1.1) Applying network policies.
echo "----------------------- Setting up Cluster ----------------------------"
echo "1: TEST: Applying network policies..."
./scripts/apply-all-policies.sh test/networkpolicies > /dev/null
# Check if the script ran successfully
if [ $? -eq 0 ]; then
    echo "Successfully applied network policies."
else
    echo "There was a problem with applying the network policies."
fi
echo "----------------------- Cluster setup done. ---------------------------"





# 2) Setting up the measurer (to measure CPU- and mem-usage) and write to file.
echo "----------- Running the Measurer as a background process ---------------"
python3 measurer/measure_system_performance.py --interval 1 > measurer.log 2>&1 &




# 3) Setting up grasshopper





# 4) Running the cluster simulator.
echo "----------- Running the Cluster Simulator as a background process ----------"
python3 simulator/cluster_simulator.py &




echo "TEST: Burst of X amount of pods created."
# echo "Sleeping for 2 seconds, to ensure everything has finished"
sleep 2



# 5) Cleaning up. Will be done by cleanup()-function when script exits.