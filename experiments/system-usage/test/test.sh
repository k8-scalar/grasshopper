
# Test script: Sets up the cluster, the measurer and calls the cluster simulator
#              in order to simulate a burst of pods being created. The measurer will measure
#              CPU-usage and memory-usage and write the results to the results/ directory.


# Function to clean up background processes
cleanup() {
    echo "Cleaning up background processes..."
    # Kill all background processes started by this script
    kill $(jobs -p) 2>/dev/null
}

# Trap script termination (e.g., CTRL+C or exit) and call cleanup
trap cleanup EXIT


# 1) Setting up the cluster.

# 1.1) Applying network policies.
echo "1: TEST: Applying network policies..."
./scripts/apply-all-policies.sh test/networkpolicies > /dev/null

# Check if the script ran successfully
if [ $? -eq 0 ]; then
    echo "Successfully applied network policies."
else
    echo "There was a problem with applying the network policies."
fi

# 2) Setting up the measurer (to measure CPU- and mem-usage) and write to file.

echo "2: TEST: Running the measurer and logging output"
python3 measurer/meaure_system_performance.py --interval 1 > measurer.log 2>&1 &

# 3) Setting up grasshopper

# echo "Running grasshopper in a different terminal."
# python3 ../../grasshopper/grasshopper-code/code/main

# 4) Running the cluster simulator. (Creating a burst of X amount of pods...)
echo "TEST: Running cluster simulator: Creating burst of X amount of pods ..."


echo "TEST: Burst of X amount of pods created."
# echo "Sleeping for 2 seconds, to ensure everything has finished"
sleep 10

# 5) Cleaning up

# 5.1) Deleting networkpolicies and pods.
echo "TEST: Restting cluster."
./scripts/reset_cluster.sh
