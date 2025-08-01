
num_pods_to_burst=("50" "100" "200")
iterations=5

# Loop through the pods array
for num_pods in "${num_pods_to_burst[@]}"; do
    echo "Doing experiment for $num_pods pods, with $iterations iterations."
    ./test/test-burst-iterations.sh $num_pods $iterations
done