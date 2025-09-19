
NUM_PODS=$1
ITERATIONS=$2
NAMESPACE="test-thesis"
ITERATION="1"
REST_TIME=40
SLEEP_TIME=10
GH_OUTPUT_FILE_LOCATION="/mnt/nfs_share/recovery_times/startup_time.txt"
GH_SETUP_POD_YAML="/home/ubuntu/master-thesis-quinten-lauwaert/grasshopper-operator/Deployment/pods/gh-v3-setup.yaml"
GH_RECOVERY_POD_YAML="/home/ubuntu/master-thesis-quinten-lauwaert/grasshopper-operator/Deployment/pods/gh-v3-recovery-times.yaml"

GH_SETUP_LOG_FILE="/home/ubuntu/master-thesis-quinten-lauwaert/experiments/recovery-time/logs/setup-logs/cluster-$NUM_PODS-pods-3-apps.log"

# Cleanup function to reset the cluster
cleanup() {
    echo "Cleaning up..."
    
    # Stop log collection if running
    if [ ! -z "$LOG_PID" ] && kill -0 "$LOG_PID" 2>/dev/null; then
        echo "Stopping log collection with PID $LOG_PID"
        kill "$LOG_PID" 2>/dev/null
    fi
    
    # Stop recovery log collection if running
    if [ ! -z "$RECOVERY_LOG_PID" ] && kill -0 "$RECOVERY_LOG_PID" 2>/dev/null; then
        echo "Stopping recovery log collection with PID $RECOVERY_LOG_PID"
        kill "$RECOVERY_LOG_PID" 2>/dev/null
    fi
    
    # Kill any running simulator processes
    if [ ! -z "$SIMULATOR_PID" ] && kill -0 "$SIMULATOR_PID" 2>/dev/null; then
        echo "Stopping simulator with PID $SIMULATOR_PID"
        kill "$SIMULATOR_PID" 2>/dev/null
    fi
    
    # Delete grasshopper pods
    echo "Deleting grasshopper pods..."
    kubectl delete pod grasshopper-pod --ignore-not-found
    kubectl delete pod grasshopper-pod-recovery-times --ignore-not-found
    
    # Reset the cluster
    echo "Resetting cluster..."
    ./scripts/reset_cluster.sh

    python3 "/home/ubuntu/master-thesis-quinten-lauwaert/grasshopper-operator/grasshopper-pod/code/openstackfiles/remove_excess_sgs.py"

    echo "RECOVERY TEST V3: Clearing Database."
    python3 "/home/ubuntu/master-thesis-quinten-lauwaert/grasshopper-operator/grasshopper-pod/code/database_helpers.py"

    echo "Cleanup completed."
}

# Set up trap to call cleanup function on script exit or interruption
trap cleanup EXIT INT TERM

TARGET_DIR="/home/ubuntu/master-thesis-quinten-lauwaert/experiments/recovery-time/results/cluster-$NUM_PODS-pods-3-apps"

# Making sure the results and logs directories exist.
mkdir -p "$TARGET_DIR"
mkdir -p "/home/ubuntu/master-thesis-quinten-lauwaert/experiments/recovery-time/logs/setup-logs"
mkdir -p "/home/ubuntu/master-thesis-quinten-lauwaert/experiments/recovery-time/logs/recovery-logs"

# First setting up the cluster once, to simulate recoveries.
# 1) Delete any existing Grasshopper pod and start the setup pod
echo "----------------------- Starting Grasshopper Setup Pod ----------------------------"

echo "1: Deleting any existing Grasshopper pods..."
kubectl delete pod grasshopper-pod --ignore-not-found
kubectl delete pod grasshopper-pod-recovery-times --ignore-not-found

echo "2: Starting Grasshopper setup pod..."
kubectl apply -f $GH_SETUP_POD_YAML

echo "3: Waiting for Grasshopper pod to be ready..."
kubectl wait --for=condition=Ready pod/grasshopper-pod --timeout=600s

if [ $? -eq 0 ]; then
    echo "Grasshopper setup pod is ready!"
else
    echo "ERROR: Grasshopper setup pod failed to become ready within timeout."
    exit 1
fi

echo "4: Giving Grasshopper 5 seconds to initialize..."
sleep 5

echo "5: Starting log collection for Grasshopper setup pod..."
kubectl logs -f grasshopper-pod > "$GH_SETUP_LOG_FILE" 2>&1 &
LOG_PID=$!
echo "Log collection started with PID $LOG_PID, saving to $GH_SETUP_LOG_FILE"

echo "----------------------- Grasshopper setup pod started. ---------------------------"

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

# 3) Stop the setup grasshopper pod, cluster setup done
echo "Stopping log collection..."
if [ ! -z "$LOG_PID" ]; then
    kill $LOG_PID 2>/dev/null || true
    LOG_PID=""
fi

echo "Deleting Grasshopper setup pod..."
kubectl delete pod grasshopper-pod --ignore-not-found

echo "Cluster setup done. Now moving on to recording recovery times"

# Iterations loop.
for ((i=1; i<=ITERATIONS; i++)) do
    echo "RECOVERY TIME TEST: Starting iteration $i"
    GH_REC_LOG_FILE="/home/ubuntu/master-thesis-quinten-lauwaert/experiments/recovery-time/logs/recovery-logs/cluster-$NUM_PODS-pods-3-apps-iter-$i.log"

    echo "Starting Grasshopper recovery times pod..."
    kubectl apply -f $GH_RECOVERY_POD_YAML
    
    echo "Waiting for Grasshopper recovery pod to be ready..."
    kubectl wait --for=condition=Ready pod/grasshopper-pod-recovery-times --timeout=600s
    
    if [ $? -eq 0 ]; then
        echo "Grasshopper recovery pod is ready!"
    else
        echo "ERROR: Grasshopper recovery pod failed to become ready within timeout."
        exit 1
    fi
    
    # Start collecting logs from the recovery pod
    kubectl logs -f grasshopper-pod-recovery-times > "$GH_REC_LOG_FILE" 2>&1 &
    RECOVERY_LOG_PID=$!
    
    # Wait for the pod to complete (check its status and results file)
    echo "Waiting for grasshopper recovery measurement to complete..."
    
    # Add a timeout to prevent infinite waiting
    TIMEOUT=300  # 5 minutes timeout
    ELAPSED=0
    
    # Clear the results file at the start
    > $GH_OUTPUT_FILE_LOCATION
    
    while [ $ELAPSED -lt $TIMEOUT ]; do
        POD_STATUS=$(kubectl get pod grasshopper-pod-recovery-times --no-headers 2>/dev/null | awk '{print $3}')
        echo "Pod status: $POD_STATUS (elapsed: ${ELAPSED}s)"
        
        # Check if results file has been written (non-empty)
        if [ -s "$GH_OUTPUT_FILE_LOCATION" ]; then
            echo "Results file has been written! Recovery measurement complete."
            break
        fi
        
        # Also check if pod is no longer running
        if [[ "$POD_STATUS" != "Running" ]] && [[ "$POD_STATUS" != "ContainerCreating" ]]; then
            echo "Pod completed with status: $POD_STATUS"
            break
        fi
        
        sleep 5
        ELAPSED=$((ELAPSED + 5))
    done
    
    if [ $ELAPSED -ge $TIMEOUT ]; then
        echo "WARNING: Pod did not complete within timeout ($TIMEOUT seconds)"
        echo "Current pod status: $(kubectl get pod grasshopper-pod-recovery-times --no-headers 2>/dev/null)"
        echo "Results file size: $(ls -l $GH_OUTPUT_FILE_LOCATION 2>/dev/null || echo 'File not found')"
    fi
    
    echo "Iteration $i done."

    # Stop log collection for this iteration
    if [ ! -z "$RECOVERY_LOG_PID" ]; then
        kill $RECOVERY_LOG_PID 2>/dev/null || true
    fi

    # Ensure the results file has content before copying
    echo "Verifying results file has content..."
    if [ ! -s "$GH_OUTPUT_FILE_LOCATION" ]; then
        echo "WARNING: Results file is empty or missing. Waiting a bit longer..."
        sleep 5
        if [ ! -s "$GH_OUTPUT_FILE_LOCATION" ]; then
            echo "ERROR: Results file is still empty after waiting. Skipping copy for iteration $i."
            echo "File status: $(ls -l $GH_OUTPUT_FILE_LOCATION 2>/dev/null || echo 'File not found')"
            continue
        fi
    fi

    # Grasshopper has now written test-results to output-file, so copying this file to proper location.
    echo "Copying results to output file"
    TARGET_FILE_LOCATION="$TARGET_DIR/iteration-$i.csv"
    cp "$GH_OUTPUT_FILE_LOCATION" "$TARGET_FILE_LOCATION"

    echo "Clearing output file..."
    > $GH_OUTPUT_FILE_LOCATION

    # Clean up the recovery pod for the next iteration
    echo "Deleting Grasshopper recovery pod..."
    kubectl delete pod grasshopper-pod-recovery-times --ignore-not-found

    echo "Sleeping for $SLEEP_TIME seconds before starting the next iteration."
    sleep $SLEEP_TIME    
done

echo "All iterations completed successfully."


