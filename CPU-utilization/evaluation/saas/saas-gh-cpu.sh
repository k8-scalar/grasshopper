#!/bin/bash

echo ==============================
echo


path_variable=/home/ubuntu/grasshopper



for ((i=1; i<=1; i++)); do

echo ======evaluation round $i==========

find "${path_variable}/data/" -type f -delete

kubectl delete svc experiment-controller --ignore-not-found

expctrl=$(helm list -aq | grep experiment-controller)
if [ -n "$expctrl" ]; then
    helm uninstall $expctrl
else
    echo "No Helm releases with 'experiment-controller' found."
fi

cd ${path_variable}/k8-scalar/studies/WOC2019/Experiments/Operations/saas-app/kube_deployment/
for sla in `ls slas` 
  do 
    if [ "$sla" == "limitrange_test" ]; then #creating only for namespace test
        namespace=`sed -e 's#.*_\(\)#\1#' <<< ${sla}`
        echo SLA configuration ${namespace}
        echo ==============================
        kubectl create -f slas/${sla}/namespace.yaml
        kubectl create -f slas/${sla}/limits.yaml --namespace=${namespace}
        kubectl create -f deploy_saas_kube.yaml --namespace=${namespace}
        kubectl create -f expose.yaml --namespace=${namespace}
        sleep 5
        kubectl get pods --namespace=${namespace}
        kubectl describe service saas --namespace=${namespace}
        
        echo ====creating secret for experiment controller======
        kubectl apply -f ${path_variable}/evaluation/saas/kubeconfig-secret.yaml
        export k8_scalar_dir=${path_variable}/k8-scalar
        helm install ${k8_scalar_dir}/studies/WOC2019/Experiments/Operations/experiment-controller --generate-name
        
        echo ====creating horizontal pod autoscaler======
        kubectl autoscale deployment saas -n test --cpu-percent=50 --min=1 --max=10
        sleep 5
        kubectl cp ${path_variable}/evaluation/saas/experiment.properties -n test experiment-controller-0:etc
        sleep 5

   	echo =====creating network policies=====
   	kubectl create -f ${path_variable}/expt/expt-controller-policy.yaml
   	kubectl create -f ${path_variable}/expt/saas-app-policy.yaml
   	#kubectl create -f ${path_variable}/expt/coreDNS_Networkpolicy.yaml
   	#Instead of adding the above policy, a namespace selector role=admin is added to host NP. So ensure to add a label role=admin to the kube-system ns 

        kubectl exec -n test -it experiment-controller-0 -- java -jar lib/scalar-1.0.0.jar etc/platform.properties etc/experiment.properties
        kubectl cp -n test experiment-controller-0:results-etc-experiment-properties.dat ${path_variable}/results/results-etc-experiment-properties.dat
    fi
done
  
echo ==============================
echo "Do you wish to delete SaaS application and test ns? [y/n]"

if read -t 10 -n 1 -r reply; then
    echo   
    if [[ $reply =~ ^[Yy]$ ]]; then
    	python3 ${path_variable}/ostackfiles/attach_defaultSG.py # deletion especially for ns can be problematic without communication among workers
        . delete_deployment.sh
    else
        echo "=============================="
        echo "==== SaaS application and ns test not removed ===="
    fi
else
    echo   
    echo "No input within 10 seconds. Deleting..."
    python3 ${path_variable}/ostackfiles/attach_defaultSG.py # deletion especially for ns can be problematic without communication among workers
    . delete_deployment.sh
fi
done
