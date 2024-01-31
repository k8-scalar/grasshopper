opaPath=`pwd`
sed  "s#opa\/policies#$opaPath\/policies#g" nginx-deployment.yaml > nginx-deployment-1.yaml
kubectl create -f nginx-deployment-1.yaml -n opa
kubectl create -f nginx-service.yaml -n opa 
rm nginx-deployment-1.yaml
kubectl get pods -n opa

