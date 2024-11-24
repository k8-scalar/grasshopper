## Install a K8s cluster on Openstack with native routing enabled

See [setup/install_kubeadm/readme.md](setup/install_kubeadm/readme.md)

## Install Grasshopper

run `./setup/run.sh`  to install all the packages and python modules that GrassHopper depends upon. We have tested this script for ubuntu24.04

## Before running Grasshopper

1. Ensure the master node of the K8s cluster has network access to the API of the Openstack Cloud typically via port 5000. If you have followed the instructions at [setup/install_kubeadm/readme.md](setup/install_kubeadm/readme.md)
, this is the case

2. Ensure you have set your openstack authentication info and application credentials for accessing the control plane API of the Openstack cloud. 

First you need to set application crendentials that are scoped to your project. You do this via the Identities menu of the Horizon dashboard service of Openstack. In case you have multiple projects in your Identies > Projects submenu, first activate the relevant project, then create the application credentials. Dowload the cloud.yaml file to save your secret.

Then from the cloud yaml file, you can extract and set the values for the following environment variables.
```
cp .env.dist .env
```
```
OS_AUTH_URL=<auth_url from clouds.yaml file>
OS_AUTH_TYPE=<auth type from clouds.yaml file>
OS_IDENTITY_API_VERSION=<identity_api_version from clouds.yaml file>
OS_REGION_NAME=<region_name from clouds.yaml file>
OS_INTERFACE=p<interface from clouds.yaml file>
OS_APPLICATION_CREDENTIAL_ID=<application_credential_id from clouds.yaml file>
OS_APPLICATION_CREDENTIAL_SECRET=<application_credential_secret from clouds.yaml file>
```

3. Run `setup_gh.py`. This creates and attaches MasterSG and WorkerSG security group with appropriate rules for an operational k8s cluster and detaches the default security group from all the worker nodes of your cluster.

## How to use GH

In one terminal, run this command (This should be run before deploying applications):

```
.gh.sh
```

Optionally, two parameters can be supplied, pernodesg (default: true) and distributed (default: false)

```
.gh.sh pernodesg=true distributed=true
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

Note that by default, GH monitors resources in all namespaces.

## Evaluation scripts

The experiment code can be found in the evaluation directory. E.g to run the evaluation for the teastore application, running the following command;

```
#set GRASSHOPPER variable
export GRASSHOPPER=$HOME/grasshopper
. grasshopper/evaluation/teastore/teastore-gh.sh
```
