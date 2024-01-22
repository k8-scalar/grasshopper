#!/bin/bash

echo ==============================
echo

read -p "Do you want to use 'pernode scenario'? (y/n): " pernode_input

#path_variable=$(python3 -c "from config import file_path; print(file_path)")
path_variable=$(python3 -c "from pathlib import Path; import sys; sys.path.append('/home/ubuntu/'); from ghv3.config import file_path; print(file_path)")


if [ "$pernode_input" == "y" ] || [ "$pernode_input" == "Y" ]; then
    logfile=${path_variable}/results/per-node/teastore-ghfly.log
    command="python3 ${path_variable}/ostackfiles/deleteRulesManually.py"
else
    logfile=${path_variable}/results/per-labelSet/teastore-ghfly.log
    command=""
fi

find "${path_variable}/data/" -type f -delete

for ((i=1; i<=2; i++)); do
	echo ======evaluation round $i==========
	echo >> $logfile
	echo ======evaluation round $i========== >> $logfile
	echo >> $logfile


echo =========================================
echo =====Deleting old pods if any ======
#helm delete teastore -n test
expctrl=$(helm list -aq | grep teastore)
if [ -n "$expctrl" ]; then
    helm uninstall $expctrl
else
    echo "No Helm releases with 'teastore' found."
fi

kubectl delete ns test &> /dev/null
kubectl delete hpa --all -n test &> /dev/null
$command

cd ${path_variable}/microservices/
kubectl create ns test
sleep 5
helm install teastore teastore-helm/ -n test
sleep 30
kubectl get po -n test

echo ======label the locust pod=======
#kubectl label ns kube-system role=admin
kubectl -n test label po $(kubectl get pods -n test | grep teastore-locust | awk '{print $1}') app=teastore

echo =====Apply network policies ========
kubectl apply -f deny-all.yml
kubectl apply -f teastore-locust-policy.yml
kubectl apply -f teastore-policy.yml 

echo ====creating horizontal pod autoscaler======

kubectl autoscale deployment teastore-webui -n test --cpu-percent=50 --min=1 --max=10
kubectl autoscale deployment teastore-locust -n test --cpu-percent=50 --min=1 --max=5
sleep 5


echo ====Evaluating the application======

kubectl exec -it -n test $(kubectl get pods -n test | grep teastore-locust | awk '{print $1}') -- bash -c " cd locust && locust -f test.py --csv=example --host=http://teastore-webui.test.svc.cluster.local:8080 -c 10  -r 10 --run-time 4m --no-web --csv=teastore" >> $logfile

echo =====Evaluation finished=======
sleep 2

echo =====Next you can delete teastore app=====
sleep 2

echo "Do you wish to delete teastore application and test ns? [y/n]"

if read -t 10 -n 1 -r reply; then
    echo   
    if [[ $reply =~ ^[Yy]$ ]]; then
      	helm delete teastore -n test;
  	kubectl delete hpa --all -n test;
  	kubectl delete ns test;
  	cd;
  	sleep 2
    else
        echo "=============================="
        echo "==== teastore application and ns test not removed ===="
    fi
else
    echo   
    echo "No input within 10 seconds. Deleting..."
      	helm delete teastore -n test;
  	kubectl delete hpa --all -n test;
  	kubectl delete ns test; 
  	cd;
  	sleep 2
fi
done
$command

