
# num_pods_to_burst=("10" "20" "50" "100" "200" "500")
num_pods_to_burst=("20" "50" "100" "200" "500")
iterations=("3" "3" "3" "3" "3")
# num_pods_to_burst=("300")
# iterations=("3")

# Loop through both lists using an index
for i in "${!num_pods_to_burst[@]}"; do
    num_pods="${num_pods_to_burst[$i]}"
    iteration="${iterations[$i]}"
    echo "Doing experiment for $num_pods pods, with $iteration iterations."
    ./test/test-burst-iterations.sh $num_pods $iteration
done