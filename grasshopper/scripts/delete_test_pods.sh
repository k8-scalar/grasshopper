kubectl get pods -n default --no-headers | awk '{print $1}' | grep -v '^grasshopper-operator$' | xargs kubectl delete pod -n default
