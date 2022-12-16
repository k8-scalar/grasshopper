for n in {1..8};
do
for i in {1..5};
do
sleep 60
kubectl apply -f - <<EOF
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
  containers:
  - image: nginx:1.14.2
    name: nginx-$i
    ports:
    - containerPort: 80
EOF

sleep 10

kubectl apply -f - <<EOF
---    
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
          User: user1
          key4: value0
  ingress:
  - from:
    - podSelector:
        matchLabels:
          User: user1
          key4: value0
EOF
done
#kubectl get pods -n test --field-selector=status.phase!=Running | awk '/^nginx/{system("kubectl delete pod -n test " $1)}'
kubectl get po -n test | awk '/^nginx/{system("kubectl delete pod -n test " $1)}';
kubectl get networkpolicies -n test | awk '/^nginx/{system("kubectl delete networkpolicies -n test " $1)}';
done
echo ==============================
read -p "Do you wish to delete on fly pods and polices? [y/n] " -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
  #for i in {1..80};
  #do  
  #kubectl delete pods -n test -l key=value$i;
  #done
  kubectl get po -n test | awk '/^nginx/{system("kubectl delete pod -n test " $1)}';
  kubectl get networkpolicies -n test | awk '/^nginx/{system("kubectl delete networkpolicies -n test " $1)}';
else
  echo ==============================;
  echo ====on fly pods and policies not removed====;
fi

