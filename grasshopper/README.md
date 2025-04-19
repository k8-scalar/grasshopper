## Install a K8s cluster on Openstack with native routing enabled

See [setup/install_kubeadm/readme.md](setup/install_kubeadm/readme.md)

Make sure your kubernetes cluster is properly setup.

## Providing Openstack Credentials to your Grasshopper Pod (through a kubernetes secret).

1) First make sure you have downloaded your Openstack application credentials through the 
   Openstack Horizon Dashboard.

2) Create a .env file (from the provided template [.env.dist]), and make sure the
   value are filled in with the values provided by the clouds.yaml file.

3) Find out where the Neutron and Nova services are running by executing the command:
    > openstack catalog list
  
   Search for the public endpoint of both services and fill in the values in the 
   OS_NEUTRON_ENDPOINT and OS_NOVA_ENDPOINT environment variables respectively.

3) Create a kubernetes secret from this file, with the following command:
    kubectl create secret generic grasshopper-openstack-creds \
        --from-env-file=.env 
    
4) Verify that the secret was successfully created:
    kubectl get secret grasshopper-openstack-creds 

5) The environment variables should get be injected by kuberenetes into the grasshopper pod
   upon startup.

# TODO: Figure out a way to make this part of the initial setup.
<!-- 3. Run `setup_gh.py`. This creates and attaches MasterSG and WorkerSG security group with appropriate rules for an operational k8s cluster and detaches the default security group from all the worker nodes of your cluster. -->


# Building and distributing the Grasshopper image. (For now we're building the image ourselves and distributing it)

1) Ensure you have docker installed.

2) Navigate to the grasshopper-pod directory and execute the following command:
    > docker build -t grasshopper:latest .

   Your grasshopper image should now be building.

3) When succesfully built, the image has to be distributed to the node where you want to
   run the grasshopper pod on. 

   1) Make sure the script is executable:
        > chmod +x scripts/distribute_image.sh

   2) Execute the following command: (This can take a while ...)
        ./scripts/distribute_image.sh grasshopper:latest <name_of_your_node>

    
## Deploying the Grasshopper pod

1) Give the grasshopper pod the necessary rights inside the cluster, by executing the command: 
    > kubectl apply -f Deployment/rbac/grasshopper-rbac.yaml

2) Start the Grasshopper Pod by executing the following command:
    > kubectl apply -f Deployment/pods/grasshopper-operator.yaml

   This start the grasshopper operator pod (in PLS mode). 
   
   You can also start a grasshopper pod, which runs with the original watching 
   mechanism by executing the following command: 
    > kubectl apply -f Deployment/pods/grasshopper-original.yaml

   If you want to change modes (PNS/PLS), change the args field in the pod yaml file
   to ["--mode", "PLS"] or ["--mode", "PNS"]




