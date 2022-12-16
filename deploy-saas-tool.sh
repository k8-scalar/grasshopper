#! /bin/bash
rm /home/ubuntu/current/src_dir/*
rm /home/ubuntu/current/data/*
cd k8-scalar/studies/WOC2019/Experiments/Operations/saas-app/kube_deployment/
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
   sleep 5

   echo ====creating horizontal pod autoscaler======
   kubectl autoscale deployment saas -n test --cpu-percent=50 --min=1 --max=12
   sleep 5

   kubectl cp ~/experiment.properties -n test experiment-controller-0:etc   
   sleep 5

   echo =====creating network policies=====
   kubectl create -f ~/current/expt/host-network-policy.yaml
   kubectl create -f ~/current/expt/client-network-policy.yaml
   #kubectl create -f ~/current/expt/coreDNS_Networkpolicy.yaml
   #Instead of adding the above policy, a namespace selector role=admin is added to host NP. So ensure to add a label role=admin to the kube-system ns 

   kubectl exec -n test -it experiment-controller-0 -- java -jar lib/scalar-1.0.0.jar etc/platform.properties etc/experiment.properties   
  done
echo =====Next you can delete SaaS app=====
sleep 2
read -p "Do you wish to delete SaaS application and test ns? [y/n] " -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
  . ~/delete-saas.sh;
else
  echo ==============================;
  echo ====SaaS application and ns test not removed====;
fi
