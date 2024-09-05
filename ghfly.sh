#!/bin/bash

rm data/*

namespace="test"
if kubectl get namespace "$namespace" &> /dev/null; then
    echo "Namespace $namespace already exists. Skipping creation."
else
    kubectl create namespace "$namespace"
fi


for n in {1..100}; do
  for i in {1..5}; do
    sleep 5

    # Pod 1
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: nginx-$i
  namespace: test
  labels:
    app: nginx
    User: user$i
    key: value$i
spec:
  affinity:
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - nginx
          - key: User
            operator: In
            values:
            - user$i
          - key: key
            operator: In
            values:
            - value$i
        topologyKey: "kubernetes.io/hostname"
  containers:
  - image: nginx:1.14.2
    imagePullPolicy: IfNotPresent
    name: nginx-$i
    ports:
    - containerPort: 80
EOF

    # Pod 2
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: nginx2-$i
  namespace: test
  labels:
    app: nginx
    User$i: user$i
    key$i: value$i
spec:
  affinity:
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - nginx
          - key: User$i
            operator: In
            values:
            - user$i
          - key: key$i
            operator: In
            values:
            - value$i
        topologyKey: "kubernetes.io/hostname"
  containers:
  - image: nginx:1.14.2
    imagePullPolicy: IfNotPresent
    name: nginx2-$i
    ports:
    - containerPort: 80
EOF

    sleep 10

    # NetworkPolicy for Pod 1
    cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: nginx-policy-$i
  namespace: test
spec:
  podSelector:
    matchLabels:
      app: nginx
      User: user$i
      key: value$i
  policyTypes:
  - Egress
  - Ingress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: nginx
          User$i: user$i
          key$i: value$i
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: nginx
          User$i: user$i
          key$i: value$i
EOF

    # NetworkPolicy for Pod 2
    cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: nginx2-policy-$i
  namespace: test
spec:
  podSelector:
    matchLabels:
      app: nginx
      User$i: user$i
      key$i: value$i
  policyTypes:
  - Egress
  - Ingress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: nginx
          User: user$i
          key: value$i
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: nginx
          User: user$i
          key: value$i
EOF
  done

sleep 30
kubectl get po -n test | awk '/^nginx/{system("kubectl delete pod -n test --grace-period=0 --force " $1)}';

kubectl get networkpolicies -n test | awk '/^nginx/{system("kubectl delete networkpolicies -n test " $1)}';
sleep 30
done

echo ==============================
read -p "Do you wish to delete on fly pods and polices? [y/n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
  kubectl get po -n test | awk '/^nginx/{system("kubectl delete pod -n test --grace-period=0 --force " $1)}';
  kubectl get networkpolicies -n test | awk '/^nginx/{system("kubectl delete networkpolicies -n test " $1)}';
else
  echo ==============================;
  echo ====on fly pods and policies not removed====;
fi
