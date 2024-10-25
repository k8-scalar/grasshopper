#!/bin/bash

echo ==============================
echo

read -p "Do you want to use 'pernode scenario'? (y/n): " pernode_input

path_variable=$GRASSHOPPER

if [ "$pernode_input" == "y" ] || [ "$pernode_input" == "Y" ]; then
    logfile=${path_variable}/experiments/results/per-node/teastore-gh
    command="python3 ${path_variable}/ostackfiles/deleteRulesManually.py"
else
    logfile=${path_variable}/experiments/results/per-labelSet/teastore-gh
    command=""
fi

python3 ${path_variable}/ostackfiles/detach_defaultSG.py #attach default SG to workers if not attached

for ((i=1; i<=20; i++)); do
    echo ======evaluation round $i==========

    find "${path_variable}/data/" -type f -delete

    echo =========================================
    echo =====Deleting old pods if any ======
    #helm delete teastore -n test
    expctrl=$(helm list -n test -aq | grep teastore)
    if [ -n "$expctrl" ]; then
        helm uninstall $expctrl
    else
        echo "No Helm releases with 'teastore' found."
    fi

    kubectl delete hpa --all -n test &> /dev/null
    $command
    
    
    cd ${path_variable}/experiments/microservices/
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


        kubectl exec -it -n test $(kubectl get pods -n test | grep teastore-locust | awk '{print $1}') -- bash -c " cd locust && locust -f test.py --csv=example --host=http://teastore-webui.test.svc.cluster.local:8080 -c 10  -r 10 --run-time 4m --no-web --csv=teastore" 
        kubectl cp -n test $(kubectl get pods -n test | grep teastore-locust | awk '{print $1}'):locust/teastore_requests.csv $logfile/teastore_requests$i.csv
        kubectl cp -n test $(kubectl get pods -n test | grep teastore-locust | awk '{print $1}'):locust/teastore_distribution.csv $logfile/teastore_distribution$i.csv

    sleep 10
    echo =====Evaluation finished=======
    sleep 2

    echo =====Next you can delete teastore app=====
    sleep 2

    echo "Do you wish to delete teastore application and test ns? [y/n]"

    if read -t 10 -n 1 -r reply; then
        echo   
        if [[ $reply =~ ^[Yy]$ ]]; then
            python3 ${path_variable}/ostackfiles/attach_defaultSG.py # deletion especially for ns can be problematic without communication among workers
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
        python3 ${path_variable}/ostackfiles/attach_defaultSG.py # deletion especially for ns can be problematic without communication among workers
        helm delete teastore -n test;
        kubectl delete hpa --all -n test;
        kubectl delete ns test;
        cd;
        sleep 2
    fi
done

