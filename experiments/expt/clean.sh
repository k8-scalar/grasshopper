#kubectl delete po --all -n test
kubectl delete pods netperf-* -n test
kubectl delete networkpolicies --all -n test

rm /home/ubuntu/current/src_dir/*
rm /home/ubuntu/current/data/*

