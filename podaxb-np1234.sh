#!/bin/bash

kubectl apply -f expt/PodA.yaml
kubectl apply -f expt/PodX.yaml
kubectl apply -f expt/PodB.yaml

sleep 5
kubectl apply -f expt/NP1.yaml
kubectl apply -f expt/NP2.yaml
kubectl apply -f expt/NP3.yaml
kubectl apply -f expt/NP4.yaml
