#!/bin/bash

#namespace=${1:-default}
#app=$2
#echo $namespace
#echo $app
#kubectl create -f storageclass.yaml -n $namespace
count=`kubectl get nodes | wc -l`
nodes=`expr $count - 2`
for app in `seq 1 5`; do for i in `seq $nodes`; do sed "s/local-pv/local-pv-$app-$i/g" persistentvolume_client.yaml | sed "s/\"worker\"/\"worker-$i\"/g" | sed "s/ath: \/data/ath: \/data-pvg\/$app/g" > pv.yaml; kubectl create -f pv.yaml; done; done
