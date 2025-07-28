


NUM_PODS=$1


GH_LOG_FILE="/home/ubuntu/master-thesis-quinten-lauwaert/experiments/recovery-time/setup-logs/cluster_{$NUM_PODS}_3_apps.log"

# First setting up the cluster once, to simulate recoveries.

# 1) Start grasshopper.py in background and log output
echo "Starting grasshopper.py..."
python3 $GH_LOCATION --mode PLS > "$GH_LOG_FILE" 2>&1 &
GH_PID=$!
echo "Grasshopper started with PID $GH_PID"

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


# 3) Killing gh, cluster setup done
echo "Stopping grasshopper.py with PID $GH_PID"
kill "$GH_PID"
wait "$GH_PID" 2>/dev/null

echo "Cluster setup done. Now moving on to recording "recovery" times"


