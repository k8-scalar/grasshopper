
num_pods_to_burst=("10" "20" "50" "100" "200" "500")
intervals=("0.5" "1" "1" "1" "1" "1")

# Loop through both lists using an index
for i in "${!num_pods_to_burst[@]}"; do
    num_pods="${num_pods_to_burst[$i]}"
    interval="${intervals[$i]}"
    echo "Doing experiment for $num_pods pods, with interval of $interval seconds"
    ./test/test-burst-iterations.sh $num_pods $interval
done