kubectl apply -f tests/TestPods/test-pod-1.yaml
kubectl apply -f tests/TestPods/test-pod-2.yaml
# ./~/grasshopper-operator/tests/scripts/apply-all-policies ~/grasshopper-operator/tests/TestPolicies

kubectl apply -f tests/TestPolicies/NonOffendingPolicies/allow-app-1-app-2.yaml
