#! /bin/bash
for sla in `ls slas` 
  do 
   namespace=`sed -e 's#.*_\(\)#\1#' <<< ${sla}`
   echo SLA configuration ${namespace}
   echo ==============================
   kubectl delete -f slas/${sla}/limits.yaml --namespace=${namespace}
   kubectl delete -f deploy_saas_kube.yaml --namespace=${namespace}
   kubectl delete -f expose.yaml --namespace=${namespace}
   kubectl delete po --all -n test
   kubectl delete networkpolicies --all -n test
   kubectl delete -f slas/${sla}/namespace.yaml
   expctrl=$(helm list -aq 2>&1)
   helm uninstall $expctrl
   echo ==============================
   rm /home/ubuntu/current/src_dir/*
   rm /home/ubuntu/current/data/*
  done



