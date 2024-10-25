# Teastore versions
This repository contains various (modified) major releases 1.x.0 of Teastore. 
The official [repository]( https://github.com/DescartesResearch/TeaStore) is developed/maintained by the Descartes Research Group at the University of Würzburg.
Besides bug fixes to allow for stable automated deployments this repository containes:
* Helm chart for each deployment and version switching using values. 
* Locust loadtest following workflow described in [paper @ MASCOTS 2018](https://ieeexplore.ieee.org/abstract/document/8526888)


## Prerequisites 
* Operational K8's cluster on openstack
* Helm installation on K8's cluster and local machine (working remotely via kubectl)

### K8 installation on openstack (dnetcloud or xerces)
1. Create VMs for master, two or more worker nodes and locust nodes.
   1. Source: Ubuntu-20.04
   2. The master node requires at least 2 cpus and 2 GB RAM. 
   3. The worker node requires at least 4 cpus and 4GB for the values in the Helm chart and for a rolling update with 100% max surge and 0% unavailability
   4. The locust node requires at least 2 cpus and 2 GB RAM
2. Follow this [guide](https://kubernetes.io/docs/setup/independent/install-kubeadm/) to prepare the nodes to use  kubeadm to setup a k8 cluster.
   1. On each node: install container-runtime, kubeadm,kubelet and kubectl. (Currently using v1.18.9)
3. Setup a cluster using kubeadm [guide](https://kubernetes.io/docs/setup/independent/create-cluster-kubeadm/) or [Gerald's ansible guide](https://gitlab.kuleuven.be/u0018104/msca-itn-eid-5ghosts/-/tree/master/ESRs/Gerald/EU-CNC2021/Ansible%20modules/kubeadm-cluster)
4. Label the nodes
   1. label the worker node on top of which the database must always be deployed: `kubectl label node <nodename> dbNode=yes`. This node stores the persistent data of the database
   2. label the locust node: `kubectl label node <nodename> locustNode=yes`
5. If kubeadm is too complex, try installing [minikube](https://minikube.sigs.k8s.io/docs/) on a single VM of at least 12 cores and 12 GB RAM: `minikube start --driver=docker --cpus=12 --memory=12Gi`

## Install Teastore via the helm chart.
The helm-chart is located in the teastore-helm folder. The `values.yaml` file can be used to alter the version or the resource settings of components specified in the template. 

Installing helm on the master node: https://helm.sh/ 

To deploy the teastore run:

```
kubectl create  ns teastore
helm install teastore teastore-helm --namespace teastore
```
This command will create a helm release named teastore and deploy the application components in the teastore namespace. 

To list the installed releases run: 
```
helm list -n teastore
```
Wait until all the pods of the application are marked ready (by readiness probes defined in chart template). (2-3 min)
```
kubectl -n teastore get pods
```
Optionally add the watch flag to get automated refresh.
```
kubectl -n teastore get pods -w
```
To find the address to the webui
```
kubectl get services -n teastore
```

To teardown the application run:
```
helm delete teastore -n teastore
```



## Running the locust loadtest.
1. There is a pod named `teastore-locustxxxx`.
   1. ```kubectl exec -it teastore-locust-xxxx -n teastore -- bash```
   2. ```cd locust``` 
   3.  ```locust -f test.py --host=http://teastore-webui.teastore.svc.cluster.local:8080 -c 10  -r 1 --run-time 4m --no-web``` 


## Game
The goal of the exercise is to upgrade the running version from version 1.2.0 to 1.3.0 without zero-down time and without failed requests.

First switch the current default namespace to teastore:
```
kubectl config set-context --current --namespace=teastore
```
