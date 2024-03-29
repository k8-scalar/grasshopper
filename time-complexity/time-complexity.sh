#!/bin/bash

echo ==============================
echo
path_variable=/home/ubuntu/grasshopper
logfile=${path_variable}/time-complexity-output.txt

python3 ${path_variable}/ostackfiles/attach_defaultSG.py #detach default SG to workers if not attached


for ((i=1; i<=5; i++)); do
python3 ${path_variable}/ostackfiles/deleteRulesManually.py
#python3 ${path_variable}/ostackfiles/delete-pls-pols.py
find "${path_variable}/data/" -type f -delete

kubectl create ns test
sleep 15
echo step1 >> $logfile
kubectl apply -f deployment_S.yaml
sleep 15
echo step2 >> $logfile
kubectl apply -f networkPolicy_S.yaml
sleep 15
echo step3 >> $logfile
kubectl apply -f networkPolicy_T.yaml
sleep 15
echo step4 >> $logfile
kubectl apply -f deployment_T.yaml
sleep 15
echo step5 >> $logfile
kubectl scale deployment pod-s -n test --replicas=2
sleep 15
echo step6 >> $logfile
kubectl scale deployment pod-t -n test --replicas=2
sleep 15
echo step7 >> $logfile
sleep 15
echo step8 >> $logfile
kubectl apply -f networkPolicy_S2.yaml
sleep 15
echo step9 >> $logfile
kubectl apply -f networkPolicy_V.yaml
sleep 15
echo step10 >> $logfile
kubectl apply -f deployment_V.yaml
sleep 15
echo step11 >> $logfile
kubectl scale deployment pod-s -n test --replicas=3
sleep 15
echo step12 >> $logfile
kubectl apply -f deployment_S2.yaml
sleep 15
echo step13 >> $logfile
kubectl scale deployment pod-s -n test --replicas=4
sleep 15
echo step14 >> $logfile
kubectl scale deployment pod-s -n test --replicas=5
sleep 15
echo step15 >> $logfile
kubectl scale deployment pod-s -n test --replicas=6
sleep 15
echo step16 >> $logfile
kubectl scale deployment pod-s -n test --replicas=7
sleep 15
echo step17 >> $logfile
kubectl scale deployment pod-s -n test --replicas=8
sleep 15
echo step18 >> $logfile
kubectl scale deployment pod-s -n test --replicas=9
sleep 15
echo step19 >> $logfile
kubectl scale deployment pod-s -n test --replicas=10
sleep 15
echo step20 >> $logfile
kubectl scale deployment pod-s -n test --replicas=11
sleep 15
echo step21 >> $logfile
kubectl scale deployment pod-s -n test --replicas=12
sleep 15
: '
echo step22 >> $logfile
kubectl scale deployment pod-s -n test --replicas=13
sleep 15
echo step23 >> $logfile
kubectl scale deployment pod-s -n test --replicas=14
sleep 15
echo step24 >> $logfile
kubectl scale deployment pod-s -n test --replicas=15
sleep 30
#cat ${path_variable}/time-complexity-output.txt >> $logfile
 #> ${path_variable}/time-complexity-output.txt
'

kubectl delete ns test
sleep 60

done

