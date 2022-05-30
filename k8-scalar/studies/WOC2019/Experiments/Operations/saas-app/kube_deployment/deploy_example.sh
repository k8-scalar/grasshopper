#! /bin/bash
for sla in `ls slas` 
  do 
   namespace=`sed -e 's#.*_\(\)#\1#' <<< ${sla}`
   echo SLA configuration ${namespace}
   echo ==============================
   kubectl create -f slas/${sla}/namespace.yaml
   kubectl create -f slas/${sla}/limits.yaml --namespace=${namespace}
   kubectl create -f deploy_saas_kube.yaml --namespace=${namespace}
   kubectl create -f expose.yaml --namespace=${namespace}
   kubectl get pods --namespace=${namespace}
   kubectl describe service saas --namespace=${namespace}
   
   echo ====creating secret for experiment controller======
   kubectl apply -f kubeconfig-secret.yaml
   export k8_scalar_dir=~/k8-scalar
   helm install ${k8_scalar_dir}/studies/WOC2019/Experiments/Operations/experiment-controller --generate-name
   
   echo ====creating horizontal pod autoscaler======
   kubectl autoscale deployment saas -n test --cpu-percent=80 --min=1 --max=5
   sleep 5
   kubectl cp ~/experiment.properties -n test experiment-controller-0:etc
   sleep 2
   kubectl exec -n test -it experiment-controller-0 -- java -jar lib/scalar-1.0.0.jar etc/platform.properties etc/experiment.properties
  done
  
echo ==============================
read -p "Do you wish to delete SaaS application and test ns? [y/n] " -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
  . delete_deployment.sh;
else
  echo ==============================;
  echo ====SaaS application and ns test not removed====;
fi
