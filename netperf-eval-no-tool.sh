#! /bin/bash
echo ==============================
cd current/expt/

echo ======NETPERF=================
kubectl create ns test
kubectl create -f netperf-host.yaml
kubectl create -f netperf-client-same-network.yaml
kubectl create -f netperf-client-cross-network.yaml
sleep 10


echo ====same network performance====
echo ====Latency====

kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') -- netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template='{{range .items}}{{.status.podIP}}{{"\n"}}{{end}}' --field-selector spec.nodeName=worker-2) -t TCP_RR -i 10,3 -I 99,5 -l 60 -c -C -- -r 1,1 -o MIN_LATENCY,MEAN_LATENCY,MAX_LATENCY

echo ====Throughput====
kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') -- netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template='{{range .items}}{{.status.podIP}}{{"\n"}}{{end}}' --field-selector spec.nodeName=worker-2) -i 10,3 -t TCP_STREAM -I 99,5 -l 60 -c -C -- -s 512K -S 512K



echo ====cross network performance====
echo ====Latency====

kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') -- netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template='{{range .items}}{{.status.podIP}}{{"\n"}}{{end}}' --field-selector spec.nodeName=worker-3) -t TCP_RR -i 10,3 -I 99,5 -l 60 -c -C -- -r 1,1 -o MIN_LATENCY,MEAN_LATENCY,MAX_LATENCY

echo ====Throughput====
kubectl exec -n test -i -t $(kubectl get pod -n test -l "app=netperf-host" -o name | sed 's/pods\///') -- netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template='{{range .items}}{{.status.podIP}}{{"\n"}}{{end}}' --field-selector spec.nodeName=worker-3) -i 10,3 -t TCP_STREAM -I 99,5 -l 60 -c -C -- -s 512K -S 512K

sleep 10
echo ==============================
read -p "Do you wish to delete netperf-notool and test ns? [y/n] " -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
  kubectl delete po netperf-client-cross -n test;
  kubectl delete po netperf-client-same -n test;
  kubectl delete po netperf-host -n test;
  kubectl delete ns test;
else
  echo ==============================;
  echo ====Tool and ns test not removed====;
fi


