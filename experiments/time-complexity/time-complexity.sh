#! /bin/bash
#step1
kubectl apply -f deployment_S.yaml

#step2
kubectl apply -f networkPolicy_S.yaml

#step3
kubectl apply -f networkPolicy_T.yaml

#step4
kubectl apply -f deployment_T.yaml

#step5
kubectl scale deployment pod-s -n test --replicas=2

#step6
kubectl scale deployment pod-t -n test --replicas=2

#step7

#step8
kubectl apply -f networkPolicy_S2.yaml

#step9
kubectl apply -f networkPolicy_V.yaml

#step10
kubectl apply -f deployment_V.yaml

#step11
kubectl scale deployment pod-s -n test --replicas=3

#step12
kubectl apply -f deployment_S2.yaml
