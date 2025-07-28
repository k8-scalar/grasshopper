
NUM_PODS=$1
ITERATIONS=$2
NAMESPACE="test-thesis"
ITERATION="1"
REST_TIME=40
SLEEP_TIME=10
GH_OUTPUT_FILE_LOCATION="/mnt/nfs_share/recovery_times/startup_time.txt"

GH_SETUP_LOG_FILE="/home/ubuntu/master-thesis-quinten-lauwaert/experiments/recovery-time/logs/setup-logs/cluster-$NUM_PODS-pods-3-apps.log"

# Cleanup function to reset the cluster
cleanup() {
    echo "Cleaning up..."
    
    # Kill any running grasshopper processes
    if [ ! -z "$GH_PID" ] && kill -0 "$GH_PID" 2>/dev/null; then
        echo "Stopping grasshopper.py with PID $GH_PID"
        kill "$GH_PID"
        wait "$GH_PID" 2>/dev/null
    fi
    
    # Kill any running simulator processes
    if [ ! -z "$SIMULATOR_PID" ] && kill -0 "$SIMULATOR_PID" 2>/dev/null; then
        echo "Stopping simulator with PID $SIMULATOR_PID"
        kill "$SIMULATOR_PID"
        wait "$SIMULATOR_PID" 2>/dev/null
    fi
    
    # Reset the cluster
    echo "Resetting cluster..."
    ./scripts/reset_cluster.sh

    echo "Cleanup completed."
}

# Set up trap to call cleanup function on script exit or interruption
trap cleanup EXIT INT TERM

GH_LOCATION="/home/ubuntu/master-thesis-quinten-lauwaert/grasshopper/grasshopper-code/code/main.py"
GH_REC_TIME_LOCATION="/home/ubuntu/master-thesis-quinten-lauwaert/grasshopper/grasshopper-code/code/main_recovery_time.py"
TARGET_DIR="/home/ubuntu/master-thesis-quinten-lauwaert/experiments/recovery-time/results/cluster-$NUM_PODS-3-apps"

# Making sure the results directory exists.
mkdir -p "$TARGET_DIR"

# First setting up the cluster once, to simulate recoveries.
# 1) Start grasshopper.py in background and log output
echo "Starting grasshopper.py..."

python3 $GH_LOCATION --mode PLS --namespace "test-thesis" > "$GH_SETUP_LOG_FILE" 2>&1 &
GH_PID=$!
echo "Grasshopper started with PID $GH_PID"

echo "Sleeping for 5 to let GH start up."
sleep 5

# 2) Setting up the cluster.
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


# 3) Bursting X amount of pods.
echo "----------- Running the Cluster Simulator as a background process ----------"
python3 simulator/cluster_simulator.py --namespace $NAMESPACE --num-pods $NUM_PODS  2>&1 &
SIMULATOR_PID=$!  # Store the PID of the measurer process
echo "Simulator started with PID $SIMULATOR_PID."
echo "TEST: Burst of X amount of pods created."

# Sleeping, in order to give the simulator time to do it's bursts.
echo "Sleeping for $REST_TIME, in order to give simulator time to finish burst."
sleep $REST_TIME

# 3) Killing gh, cluster setup done
echo "Stopping grasshopper.py with PID $GH_PID"
kill "$GH_PID"
wait "$GH_PID" 2>/dev/null

echo "Cluster setup done. Now moving on to recording "recovery" times"

# Iterations loop.
for ((i=1; i<=ITERATIONS; i++)) do
    echo "RECOVERY TIME TEST: Starting iteration $i"
    GH_REC_LOG_FILE="/home/ubuntu/master-thesis-quinten-lauwaert/experiments/recovery-time/logs/recovery-logs/cluster-$NUM_PODS-pods-3-apps-iter-$i.log"

    echo "Starting grasshopper_recovery_times.py..."
    python3 $GH_REC_TIME_LOCATION --mode PLS > "$GH_REC_LOG_FILE" 2>&1 &
    GH_PID=$!
    echo "Grasshopper started with PID $GH_PID"

    # Wait for grasshopper to complete the recovery measurement
    echo "Waiting for grasshopper recovery measurement to complete..."
    wait $GH_PID
    echo "Iteration $i done."

    # Grasshopper has now written test-results to output-file, so copying this file to proper location.
    echo "Copying results to output file"
    TARGET_FILE_LOCATION="$TARGET_DIR/iteration-$i.csv"
    cp "$GH_OUTPUT_FILE_LOCATION" "$TARGET_FILE_LOCATION"

    echo "Clearing output file..."
    > $GH_OUTPUT_FILE_LOCATION

    echo "Sleeping for $SLEEP_TIME seconds before starting the next iteration."
    sleep $SLEEP_TIME    
done

echo "All iterations completed successfully."


