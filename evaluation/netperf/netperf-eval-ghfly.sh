#!/bin/bash

echo ==============================
echo
path_variable=/home/ubuntu/grasshopper
read -p "Do you want to use 'pernode scenario'? (y/n): " pernode_input
if [ "$pernode_input" == "y" ] || [ "$pernode_input" == "Y" ]; then
    logfile=${path_variable}/results/per-node/netperf-ghfly-v2.log
else
    logfile=${path_variable}/results/per-labelSet/netperf-ghfly-v2.log
fi

python3 grasshopper/ostackfiles/detach_defaultSG.py #detach default SG to workers if not detached

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
	echo =====creating network policies=====
	kubectl create -f host-network-policy.yaml
	kubectl create -f client-network-policy.yaml
	
	echo
	echo ====intraNode network evaluation====
	echo ====intraNode network evaluation==== >> $logfile
	echo
	echo ====measuring latency====
	echo ====measuring latency==== >> $logfile

	#for i in {1..5}; do   echo "Run $i:";   kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') --     netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template="{{range .items}}{{.status.podIP}}{{\"\n\"}}{{end}}" --field-selector spec.nodeName=worker-1)  -T2   -t TCP_RR -l 30 -c -C -- -r 1,1 -o MIN_LATENCY,MEAN_LATENCY,MAX_LATENCY | tail -n 1; done | awk -F ',' 'NR>1{for(i=1;i<=NF;i++)sum[i]+=$i; print $0} END{printf "Average: "; for(i=1;i<=NF;i++)printf "%s%.2f", (i==1)?"":",", sum[i]/5; print ""}' >> $logfile
	#echo >> $logfile

	#echo
	#echo ====measuring throughput====
	#echo ====measuring throughput==== >> $logfile
	
	#for i in {1..5}; do   echo "Run $i:";   kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') --     netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template="{{range .items}}{{.status.podIP}}{{\"\n\"}}{{end}}" --field-selector spec.nodeName=worker-1)  -T2   -t TCP_STREAM -l 30 | tail -n 1; done | awk 'NR>1{
  #for(i=1;i<=NF;i++) {
    #sum[i]+=$i;
  #}
  #print $0
#} 
#END{
  #printf "Average: ";
  #for(i=1;i<=NF;i++) {
    #printf "%s%.2f", (i==1)?"":",", sum[i]/5;
  #}
  #print "";
#}' >> $logfile

	echo
	echo ====interNode network evaluation====
	echo ====interNode network evaluation==== >> $logfile
	echo

	echo
	echo ====measuring latency====
	echo ====measuring latency==== >> $logfile

	for i in {1..5}; do   echo "Run $i:";   kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') --     netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template="{{range .items}}{{.status.podIP}}{{\"\n\"}}{{end}}" --field-selector spec.nodeName=worker-15)  -T2   -t TCP_RR -l 10 -c -C -- -r 1,1 -o MIN_LATENCY,MEAN_LATENCY,MAX_LATENCY | tail -n 1; done | awk -F ',' 'NR>1{for(i=1;i<=NF;i++)sum[i]+=$i; print $0} END{printf "Average: "; for(i=1;i<=NF;i++)printf "%s%.2f", (i==1)?"":",", sum[i]/5; print ""}' >> $logfile
	echo >> $logfile

	echo
	echo ====measuring throughput====
	echo ====measuring throughput==== >> $logfile
	for i in {1..5}; do   echo "Run $i:";   kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') --     netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template="{{range .items}}{{.status.podIP}}{{\"\n\"}}{{end}}" --field-selector spec.nodeName=worker-15)  -T2   -t TCP_STREAM -l 10 | tail -n 1; done | awk 'NR>1{
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
	python3 ${path_variable}/ostackfiles/attach_defaultSG.py # deletion especially for ns can be problematic without communication among workers
	kubectl delete po netperf-client-intra -n test 
	kubectl delete po netperf-client-inter -n test 
	kubectl delete po netperf-host -n test 	
	kubectl delete ns test
	cd ..
	find "${path_variable}/data/" -type f -delete  
	sleep 10

	echo ==============================
done

