# ! /bin/bash
#Dont forget to use watchdog-with-outputfile.py instead of the original watch-dog.py

#Because GH was tailored to pods
#Removal needs adustment to cater for mulptiple pods in case of multiple deloyment replicas
#these commands snure that old rules and SGs are removed
python3 $GRASSHOPPER/detach_time_comprexitySGs.py # per_labelset_scenario
python3 $GRASSHOPPER/deleteRulesManually.py #SGperNode scenario
find $GRASSHOPPER/data -type f -delete #just in case a file is not removed from data
sleep 10

for ((i=1; i<=1; i++)); do
echo =======eval $i ========== >> $GRASSHOPPER/time-complexity-output.txt
python3 $GRASSHOPPER/time-complexity/time-complexity.py 
sleep 300 # Keep state for 5 mins before deleting
kubectl delete ns test
sleep 10
echo >> $GRASSHOPPER/time-complexity-output.txt
done
