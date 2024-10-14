## Install Grasshopper

Grasshopper requires python3.10 

run `./setup/run.sh`  to install all the packages and python modules that GrassHopper depends upon. We have tested this script for ubuntu20.24

## Before running Grasshopper

1. Ensure you have set your credentials for accessing the control plane API of the Openstack cloud. You do this via the Identities menu. In case you have multiple projects, first activate the relevant project, then create the application credentials. Dowload the cloud.yaml file to safe yout secret.

```
export OS_APPLICATION_CREDENTIAL_ID=<your credential id>
export OS_APPLICATION_CREDENTIAL_ID
export OS_APPLICATION_CREDENTIAL_SECRET=<your credential secret>
export OS_APPLICATION_CREDENTIAL_SECRET
```
2. Ensure the master node of the K8s cluster has network access to the API of the Openstack Cloud typically via port 5000


## How to use GH

In one terminal, run this command (This should be run before deploying applications):

```
cd grasshopper/ && . gh.sh pernodesg=false
```

In the second terminal, deploy the application.

E.g the Microservices application Teastore and its network policies can be deployed as follows

```
cd grasshopper/microservices
kubectl create -f deny-all.yml
kubectl create -f teastore-policy.yml 
kubectl create -f teastore-locust-policy.yml
helm install ts teastore-helm/ -n test
```

Note that by default, GH monitors resources in test namespace. It is possible tochange the names in grasshopper/k8s.watch.py, but this will also need changing the network policies so that they are deployed in the corresponding namespace.

## Evaluation scripts

The experiment code can be found in the evaluation directory. E.g to run the evaluation for the teastore application, running the following command;

```
#set GRASSHOPPER variable
export GRASSHOPPER=$HOME/grasshopper
. grasshopper/evaluation/teastore/teastore-gh.sh
```
