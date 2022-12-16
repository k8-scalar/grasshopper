 for i in {1..30};
 do
echo ==============================;
echo EVALUATION $i
echo ==============================;
sleep 2
expctrl=$(helm list -aq 2>&1 -n demo)
helm uninstall $expctrl -n demo
kubectl delete deployments --all -n demo
kubectl delete po --all -n demo
kubectl delete networkpolicy --all -n demo 
#kubectl delete pvc -n demo --all
#kubectl delete pv --all
##./clean-directories.sh##This is too slow when the default SG is detached
#parallel-ssh -h pssh_hosts_files  -i "sudo rm -r  /data-pvg/1/*; sudo rm -r  /data-pvg/2/*; sudo rm -r  /data-pvg/3/*; sudo rm -r  /data-pvg/4/*; sudo rm -r  /data-pvg/5/*"
#./create-pvs.sh
rm /home/ubuntu/excess/current/src_dir/*
rm /home/ubuntu/excess/current/data/*

sleep 2
echo =============================================================================;
read -n 1 -s -r -rep $'\n===== Restart GH and Press any key to continue ====== \n'
echo =============================================================================;

applications=(drupal ejbca jasperreports joomla magento matomo osclass redmine wordpress wordpress-intel)
N=5

for index in $(shuf --input-range=0-$(( ${#applications[*]} - 1 )) -n ${N})
do
    for val in ${applications[$index]};
    do
    echo
    printf "\n************************\n"
    echo "Installing "$val
    printf "\n************************\n"
    helm install $val -n demo $val &>/dev/null
    sleep 10
    printf "\n************************\n"
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: $val-policy
  namespace: demo
spec:
  podSelector:
    matchLabels:
      appn: $val
  policyTypes:
  - Egress
  - Ingress
  egress:
  - to:
    - podSelector:
        matchLabels:
          stateful: $val
  ingress:
  - from:
    - podSelector:
        matchLabels:
          stateful: $val
EOF
sleep 5

cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: $val-mariadb
  namespace: demo
spec:
  podSelector:
    matchLabels:
      stateful: $val
  policyTypes:
  - Egress
  - Ingress
  egress:
  - to:
    - podSelector:
        matchLabels:
          appn: $val
  ingress:
  - from:
    - podSelector:
        matchLabels:
          appn: $val
EOF
sleep 5
    printf "\n************************\n"
    done
    sleep 5
done
sleep 10
kubectl get po -n demo
kubectl scale deployment --all -n demo --replicas=10
sleep 30
read -n 1 -s -r -rep $'\n===== Press any key to continue to the next EVALUATION ====== \n'
done
