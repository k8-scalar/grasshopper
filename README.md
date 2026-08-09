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

5) The environment variables should get be injected by kubernetes into the grasshopper pod
   upon startup. (make sure the secret is named grasshopper-openstack-creds in the gh-v2.yaml file, otherwise change the name in the "secretRef:" field to your given name. This field is found under the "envFrom:" field under the "containers:" field)

# Setup cluster Security Groups.
   See V1 README for setting up appropriate security group configuration.

# Building the Grasshopper image.

1) Ensure you have docker installed.

2) Navigate to the grasshopper-pod directory and execute the following command:
    > docker build -t grasshopper:latest .

   Your grasshopper image should now be building.

3) When succesfully built, upload the image to a registry of your choice.

   1) For example: (using Docker Hub)
   ```bash
   docker tag grasshopper:latest <your-dockerhub-username>/<repository>:<tag>
   docker push <your-dockerhub-username>/<repository>:<tag>
   ```

4) Now ensure that K8s has the right to pull the image.

   1) create a K8s secret: 
   ```bash
   kubectl create secret docker-registry regcred \
      --docker-username=<your-dockerhub-username> \
      --docker-password=<your-dockerhub-password> \
      --docker-email=<your-email>
   ```

   2) Make sure you name the secret regcred, otherwise change the name in the "imagePullSecrets" to your given name.

5)  change the "image:" field in the gh-v2.yaml file to the repository where your GH image is stored
    
## Deploying the Grasshopper pod

1) Give the grasshopper pod the necessary rights inside the cluster, by executing the command: 
    > kubectl apply -f Deployment/rbac/grasshopper-rbac.yaml

2) Start the Grasshopper Pod by executing the following command:
    > kubectl apply -f Deployment/pods/grasshopper-operator.yaml

   This starts the grasshopper operator pod (in PLS mode). 
   
   You can also start a grasshopper pod, which runs with the original watching 
   mechanism by executing the following command: 
    > kubectl apply -f Deployment/pods/grasshopper-original.yaml

   If you want to change modes (PNS/PLS), change the args field in the pod yaml file
   to ["--mode", "PLS"] or ["--mode", "PNS"]


