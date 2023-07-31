#! /bin/bash
echo ==============================
path_variable=$(python3 -c "from config import file_path; print(file_path)")

rm ${path_variable}/src_dir/*
rm ${path_variable}/data/*
cd expt/

echo ======NETPERF=================
kubectl create ns test
sleep 5

kubectl create -f netperf-host.yaml
kubectl create -f netperf-client-intranode.yaml
kubectl create -f netperf-client-internode.yaml
sleep 10

echo =====creating network policies=====
kubectl create -f host-network-policy.yaml
kubectl create -f client-network-policy.yaml

:'
echo ====same network performance====
echo ====Latency====

kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') -- netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template='{{range .items}}{{.status.podIP}}{{"\n"}}{{end}}' --field-selector spec.nodeName=worker-1) -t TCP_RR -i 10,3 -I 99,5 -l 60 -c -C -- -r 1,1 -o MIN_LATENCY,MEAN_LATENCY,MAX_LATENCY

echo ====Throughput====
kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') -- netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template='{{range .items}}{{.status.podIP}}{{"\n"}}{{end}}' --field-selector spec.nodeName=worker-1) -i 10,3 -t TCP_STREAM -I 99,5 -l 60 -c -C -- -s 512K -S 512K



echo ====cross network performance====
echo ====Latency====

kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') -- netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template='{{range .items}}{{.status.podIP}}{{"\n"}}{{end}}' --field-selector spec.nodeName=worker-2) -t TCP_RR -i 10,3 -I 99,5 -l 60 -c -C -- -r 1,1 -o MIN_LATENCY,MEAN_LATENCY,MAX_LATENCY

echo ====Throughput====
kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') -- netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template='{{range .items}}{{.status.podIP}}{{"\n"}}{{end}}' --field-selector spec.nodeName=worker-2) -i 10,3 -t TCP_STREAM -I 99,5 -l 60 -c -C -- -s 512K -S 512K
'
sleep 10

echo ==============================
read -p "Do you wish to delete netperf-notool and test ns? [y/n] " -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
  kubectl delete po netperf-client-cross -n test;
  kubectl delete po netperf-client-same -n test;
  kubectl delete po netperf-host -n test;
  kubectl delete networkpolicies --all -n test;
  kubectl delete ns test;
  rm ${path_variable}/data/*;
  sleep 5
  rm ${path_variable}/src_dir/*;
  
else
  echo ==============================;
  echo ====Tool and ns test not removed====;
fi

