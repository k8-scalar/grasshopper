#!/bin/bash

echo ==============================
echo

MORPHEUS_HOME=$HOME
path_variable=$MORPHEUS_HOME/grasshopper
helm_chart_variable=$path_variable/microservices/teastore-helm/
metrics_script=${path_variable}/evaluation/teastore/scheduling_metrics/get_metrics_v2.py

logfile=${path_variable}/results/per-labelSet/teastore-gh
rm ${logfile}/results.csv


#python3 ghv3/ostackfiles/detach_defaultSG.py #attach default SG to workers if not attached

for ((i=1; i<=6; i++)); do
    rm ${logfile}/cross-segmentation
    echo ======evaluation round $i==========

    find "${path_variable}/data/" -type f -delete

    #echo =========================================
    echo =====Deleting old pods if any ======
    #helm delete teastore -n test
    expctrl=$(helm list -n test -aq | grep teastore)
    if [ -n "$expctrl" ]; then
        helm uninstall $expctrl
    else
        echo "No Helm releases with 'teastore' found."
    fi

    #kubectl delete hpa --all -n test &> /dev/null
    
    
    cd ${path_variable}/microservices/
    #kubectl create ns test
    #echo =====scheduling random pods ======
    #expctrl1=$(kubectl get deployment | grep nginx-deployment)
    #if [ -n "$expctrl1" ]; then
    #	kubectl scale deployment nginx-deployment --replicas=`shuf -i 5-20 -n 1` -n test
    #else
#	kubectl create -f nginx-deployment.yaml -n test
 #   fi	
    #sleep 5
    helm install teastore  $helm_chart_variable -n test
    #kubectl scale deployment nginx-deployment --replicas=0 -n test
    sleep 10

    echo =====Recording scheduling performance metrics ======
    kubectl get po -n test -o wide
    cd  ${logfile}
    python3  ${path_variable}/evaluation/teastore/scheduling_metrics/get_metrics_v2.py
    if [ -f cross-segmentation ]
    then 
    	cross=`cat cross-segmentation`
    else
        cross="yes"
    fi
    echo cross-segmentation result = $cross
    cd ${path_variable}/microservices/ 
     
    echo ======label the locust pod=======
    #kubectl label ns kube-system role=admin
    kubectl -n test label po $(kubectl get pods -n test | grep teastore-locust | awk '{print $1}') app=teastore

    echo =====Apply network policies ========
    kubectl apply -f deny-all.yml
    if [ $cross == "no" ]
    then
    	kubectl apply -f teastore-locust-policy.yml
    	kubectl apply -f teastore-policy.yml
	sleep 180
    else
	echo "Segmentation broken or cluster down -> deny all policy!"
    fi	
    #kubectl apply -f ts-networkpolicy.yaml
    #kubectl apply -f ts-test.yaml
    #echo ====creating horizontal pod autoscaler======

    #kubectl autoscale deployment teastore-webui -n test --cpu-percent=50 --min=1 --max=10
    #kubectl autoscale deployment teastore-locust -n test --cpu-percent=50 --min=1 --max=5
    
    #sleep 40
    
    echo ====Evaluating the application======


    #kubectl exec -it -n test $(kubectl get pods -n test | grep teastore-locust | awk '{print $1}') -- bash -c " cd locust && locust -f test.py --host=http://teastore-webui.test.svc.cluster.local:8080 -c 5  -r 1 --run-time 1m --no-web --csv=warmup"
    #sleep 40
    if [ $cross == "no" ]
    then
	kubectl exec -it -n test $(kubectl get pods -n test | grep teastore-locust | awk '{print $1}') -- bash -c " cd locust && locust -f test.py --host=http://teastore-webui.test.svc.cluster.local:8080 -c 10  -r -1 --run-time 4m --no-web --csv=teastore"	
    	kubectl cp -n test $(kubectl get pods -n test | grep teastore-locust | awk '{print $1}'):locust/teastore_requests.csv $logfile/teastore${i}_requests.csv
    	kubectl cp -n test $(kubectl get pods -n test | grep teastore-locust | awk '{print $1}'):locust/teastore_distribution.csv $logfile/teastore${i}_distribution.csv

    	sleep 10
    else
	sleep 60
    fi
    echo =====Evaluation finished=======
    sleep 2
    
    echo =====Next you can delete teastore app=====
    sleep 2

    echo "Do you wish to delete teastore application and test ns? [y/n]"

    if read -t 10 -n 1 -r reply; then
        echo   
        if [[ $reply =~ ^[Yy]$ ]]; then
            #python3 ${path_variable}/ostackfiles/attach_defaultSG.py # deletion especially for ns can be problematic without communication among workers
            helm delete teastore -n test;
	    sleep 180
	    #kubectl delete pods --all -n test --force
	    #sleep 10
            #kubectl delete hpa --all -n test;
            #kubectl delete ns test;
	    kubectl delete -f deny-all.yml
	    if [ $cross == "no" ]
	    then
        	    kubectl delete -f teastore-locust-policy.yml
            	    kubectl delete -f teastore-policy.yml
	    fi
            cd;
            sleep 2
        else
            echo "=============================="
            echo "==== teastore application and ns test not removed ===="
        fi
    else
        echo   
        echo "No input within 10 seconds. Deleting..."
        #python3 ${path_variable}/ostackfiles/attach_defaultSG.py # deletion especially for ns can be problematic without communication among workers
	kubectl delete -f deny-all.yml
        helm delete teastore -n test;
        #kubectl delete pods --all -n test --force
        #sleep 10

	sleep 180
        #kubectl delete hpa --all -n test
        if [ $cross == "no" ]
            then
                    kubectl delete -f teastore-locust-policy.yml
                    kubectl delete -f teastore-policy.yml
            fi
        #kubectl delete ns test;
        cd;
        sleep 2
    fi
done
