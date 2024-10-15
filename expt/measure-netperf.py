import os
import time

os.system("kubectl delete po --all -n test")
os.system("kubectl delete networkpolicies --all -n test")
time.sleep(10)

os.system("kubectl apply -f netperf1.yaml")
os.system("kubectl apply -f netperf2.yaml")
time.sleep(10)

#os.system("kubectl apply -f deny-all.yaml")
os.system("kubectl apply -f testpolicy1.yaml")
os.system("kubectl apply -f testpolicy2.yaml")
time.sleep(10)

os.system("kubectl exec -n test -i -t $(kubectl get pod -n test -l \"app=netperf-host\" -o name | sed 's/pods\///') -- netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template=\'{{range .items}}{{.status.podIP}}{{\"\\n\"}}{{end}}\' --field-selector spec.nodeName=worker-1) -t TCP_RR -i 10,3 -I 99,5 -l 60 -c -C -- -r 1,1 -o MIN_LATENCY,MEAN_LATENCY,MAX_LATENCY")
os.system("kubectl exec -n test -i -t $(kubectl get pod -n test -l \"app=netperf-host\" -o name | sed 's/pods\///') -- netperf -H $(kubectl get pods -n test -l app=netperf-client -o go-template=\'{{range .items}}{{.status.podIP}}{{\"\\n\"}}{{end}}\' --field-selector spec.nodeName=worker-1) -i 10,3 -t TCP_STREAM -I 99,5 -l 60 -c -C -- -s 512K -S 512K -k THROUGHPUT,THROUGHPUT_UNITS")

