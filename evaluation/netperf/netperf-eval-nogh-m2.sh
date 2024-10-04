#!/bin/bash

echo ==============================
echo
path_variable=$GRASSHOPPER
read -p "Do you want to use 'pernode scenario'? (y/n): " pernode_input
if [ "$pernode_input" == "y" ] || [ "$pernode_input" == "Y" ]; then
    logfile=${path_variable}/results/per-node/netperf-nogh-m2.log
else
    logfile=${path_variable}/results/per-labelSet/netperf-nogh-m2.log
fi

python3 ghv3/ostackfiles/attach_defaultSG.py #attach default SG to workers if not attached


find "${path_variable}/data/" -type f -delete


for ((i=1; i<=10; i++)); do
	echo ======evaluation round $i==========
	echo >> $logfile
	echo ======evaluation round $i========== >> $logfile
	echo >> $logfile
	cd ${path_variable}/expt/
	
	echo ======NETPERF=================
	kubectl create ns test
	sleep 5

	kubectl create -f netperf-host.yaml
	kubectl create -f netperf-client-intranode.yaml
	kubectl create -f netperf-client-internode.yaml
	sleep 10

	echo
	echo ====intraNode network evaluation====
	echo ====intraNode network evaluation==== >> $logfile
	echo
	echo ====measuring latency====
	echo ====measuring latency==== >> $logfile

	for i in {1..5}; do   echo "Run $i:";   kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') --     netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template="{{range .items}}{{.status.podIP}}{{\"\n\"}}{{end}}" --field-selector spec.nodeName=worker-2)  -T2   -t TCP_RR -l 30 -c -C -- -r 1,1 -o MIN_LATENCY,MEAN_LATENCY,MAX_LATENCY | tail -n 1; done | awk -F ',' 'NR>1{for(i=1;i<=NF;i++)sum[i]+=$i; print $0} END{printf "Average: "; for(i=1;i<=NF;i++)printf "%s%.2f", (i==1)?"":",", sum[i]/5; print ""}' >> $logfile
	echo >> $logfile

	echo
	echo ====measuring throughput====
	echo ====measuring throughput==== >> $logfile
	
	for i in {1..5}; do   echo "Run $i:";   kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') --     netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template="{{range .items}}{{.status.podIP}}{{\"\n\"}}{{end}}" --field-selector spec.nodeName=worker-2)  -T2   -t TCP_STREAM -l 30 | tail -n 1; done | awk 'NR>1{
  for(i=1;i<=NF;i++) {
    sum[i]+=$i;
  }
  print $0
} 
END{
  printf "Average: ";
  for(i=1;i<=NF;i++) {
    printf "%s%.2f", (i==1)?"":",", sum[i]/5;
  }
  print "";
}' >> $logfile

	echo
	echo ====interNode network evaluation====
	echo ====interNode network evaluation==== >> $logfile
	echo

	echo
	echo ====measuring latency====
	echo ====measuring latency==== >> $logfile

	for i in {1..5}; do   echo "Run $i:";   kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') --     netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template="{{range .items}}{{.status.podIP}}{{\"\n\"}}{{end}}" --field-selector spec.nodeName=worker-3)  -T2   -t TCP_RR -l 30 -c -C -- -r 1,1 -o MIN_LATENCY,MEAN_LATENCY,MAX_LATENCY | tail -n 1; done | awk -F ',' 'NR>1{for(i=1;i<=NF;i++)sum[i]+=$i; print $0} END{printf "Average: "; for(i=1;i<=NF;i++)printf "%s%.2f", (i==1)?"":",", sum[i]/5; print ""}' >> $logfile
	echo >> $logfile

	echo
	echo ====measuring throughput====
	echo ====measuring throughput==== >> $logfile
	for i in {1..5}; do   echo "Run $i:";   kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') --     netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template="{{range .items}}{{.status.podIP}}{{\"\n\"}}{{end}}" --field-selector spec.nodeName=worker-3)  -T2   -t TCP_STREAM -l 30 | tail -n 1; done | awk 'NR>1{
  for(i=1;i<=NF;i++) {
    sum[i]+=$i;
  }
  print $0
} 
END{
  printf "Average: ";
  for(i=1;i<=NF;i++) {
    printf "%s%.2f", (i==1)?"":",", sum[i]/5;
  }
  print "";
}' >> $logfile
	echo >> $logfile

	sleep 10

	echo
	echo ====deleting resources for round $i====
	sleep 2

	kubectl delete po netperf-client-intra -n test 
	kubectl delete po netperf-client-inter -n test 
	kubectl delete po netperf-host -n test 	
	kubectl delete ns test
	cd ..

	find "${path_variable}/data/" -type f -delete  
	sleep 10

	echo ==============================
done

