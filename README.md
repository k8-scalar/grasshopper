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
   upon startup. (make sure the secret is named grasshopper-openstack-creds in the
   Deployment/pods/grasshopper-operator-PNS.yaml file, otherwise change the name in the
   "secretRef:" field to your given name. This field is found under the "envFrom:" field
   under the "containers:" field)

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

5)  change the "image:" field in the Deployment/pods/grasshopper-operator-PNS.yaml file to the repository where your GH image is stored
    
## Deploying the Grasshopper pod

Run the install script:
```bash
Deployment/install_grasshopper.sh
```

This applies, in order: RBAC (`Deployment/rbac/grasshopper-rbac.yaml`), every
bootstrap NetworkPolicy under `Deployment/networkpolicies/` (see below), then
the Grasshopper pod itself (`Deployment/pods/grasshopper-operator-PNS.yaml` by
default - pass a different path as the script's first argument to use another
manifest, e.g. one with a different mode or image).

If you want to change modes (PNS/PLS), change the args field in the pod yaml
file to `["--mode", "PLS"]` or `["--mode", "PNS"]` before running the script
(or after, then re-run `kubectl apply -f <that file>` yourself).

### Bootstrap NetworkPolicies (CNI-specific - review before running on a new cluster)

Grasshopper depends on some baseline CNI control-plane connectivity existing
before it starts (e.g. Calico's Felix-to-Typha traffic on port 5473) -
`workerSG`'s static rules only cover the egress side, so the ingress side
only exists once the relevant NetworkPolicy has been applied and Grasshopper
has processed it (see README_v2.md for why the ordering matters). Grasshopper
itself has no built-in knowledge of any particular CNI; every file under
`Deployment/networkpolicies/` is applied by the install script exactly as
it's checked into the repo, with two placeholder tokens filled in from
whatever's live on your cluster at install time:

- `__NODE_CIDRS__` - one `- ipBlock: {cidr: <ip>/32}` entry per node's live
  InternalIP (discovered via `kubectl get nodes`) - not a guessed subnet.
- `__TYPHA_NAMESPACE__` - the namespace of a live `k8s-app=calico-typha` pod,
  if this cluster runs one. A file using this token is skipped (not an
  error) if no such pod is found - e.g. on a non-Calico cluster.

`Deployment/networkpolicies/typha-ingress.yaml` ships as the default,
covering Calico's Typha requirement out of the box. If your cluster runs a
different CNI with its own bootstrap-critical connectivity need, add your
own `*.yaml` file to that directory (or remove/replace the Typha one) -
the install script doesn't need to change to pick it up.


