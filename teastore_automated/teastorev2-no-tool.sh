printf "\n=========================================\n"

printf "\n=====Deleting teastore pods if any ======\n"
echo

helm delete teastore -n teastore
kubectl delete ns teastore
rm  ~/csvdocs/teastore*
kubectl delete hpa --all -n teastore
cd ~/microservices/
kubectl create ns teastore

sleep 5

helm install teastore teastore-helm/ -n teastore
sleep 30

kubectl get po -n teastore

printf "\n====creating horizontal pod autoscaler======\n"

kubectl autoscale deployment teastore-webui -n teastore --cpu-percent=50 --min=1 --max=10
#kubectl autoscale deployment teastore-locust -n teastore --cpu-percent=50 --min=1 --max=5
sleep 5


printf "\n====Evaluating the application======\n"

for i in {1..20};
do

echo
printf "=====Evaluation round $i==============\n"
echo
kubectl exec -it -n teastore $(kubectl get pods -n teastore | grep teastore-locust | awk '{print $1}') -- bash -c " cd locust && locust -f test.py --csv=example --host=http://teastore-webui.teastore.svc.cluster.local:8080 -c 10  -r 10 --run-time 4m --no-web --csv=teastore$i"

printf "=====Evaluation round $i finished==============\n"
echo

printf "=====copying results from the container==============\n"
echo

kubectl cp teastore/$(kubectl get pods -n teastore | grep teastore-locust | awk '{print $1}'):locust/. /home/ubuntu/csvdocs/
sleep 5

#echo
#printf "=====Waiting for autoscaled pods to downscale==============\n"
#echo
#sleep 300

printf "=====cleaning for next evaluation round==============\n"

kubectl delete pod --all -n teastore --grace-period=0 --force
sleep 60

done

sleep 5

printf "\n=====Evaluation finished=======\n"
sleep 2

printf "\n=====Next you can delete teastore app=====\n"
sleep 2

read -p "Do you wish to delete teastore application and test ns? [y/n] " -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
  helm delete teastore -n teastore;
  kubectl delete hpa --all -n teastore;
  kubectl delete ns teastore;
  cd;
  rm  ~/csvdocs/teastore*;
  sleep 2


else
  printf "==============================\n"
  printf "\n====teastore application and ns teastore not removed====\n"
  cd;
  
fi

