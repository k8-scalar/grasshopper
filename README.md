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

## Run the bootstrap script for baseline cluster connectivity

Before Grasshopper's dynamic per-policy rules do anything, your cluster needs
its usual control-plane connectivity (API server 6443, kubelet 10250/10259,
etcd 2379, BGP 179, DNS 53) to actually work between control-plane and worker
nodes. This is what `setup_gh.py` / `create_master_and_workerSG.py` sets up,
and it's now multi-domain aware too:

```bash
python3 setup_gh.py
```

It groups your nodes by the same `grasshopper.io/openstack-project` label,
creates `masterSG`/`workerSG` **per project** (only in projects that actually
have a matching node), and wires up the necessary rules: same-project
master↔worker pairs via a direct security-group reference (unchanged from the
single-project case), cross-project pairs via a CIDR rule for each individual
peer node's real IP (control-plane services listen on the node's own network
stack, not a Calico pod overlay, so this doesn't need VXLAN handling the way
the dynamic per-pod rules do).

`setup_gh.py` also (re-)attaches `default` to every worker first, in case a
previous Grasshopper deployment on this cluster already detached it - see the
next section for why this matters, and note that `setup_gh.py` deliberately
does **not** detach `default` itself; Grasshopper does that on its own
startup (step 5), not this script.

### Why `default` has to stay on workers until Grasshopper detaches it

`workerSG`'s rules above are a fixed, static list. They do not - and cannot -
include the dynamic, per-node ingress rules Grasshopper creates from whatever
NetworkPolicies you apply (e.g. the Typha ipBlock policy - see the main
README/your Calico install for why Typha needs one). Until Grasshopper has
actually processed those policies, a worker relying on only `workerSG` has no
rule covering that traffic at all - `default` is what covers the gap in the
meantime.

Confirmed live, with a real connection probe (not just reading the code): with
`default` removed from a worker and that worker's dynamic Typha-ingress rule
also removed (simulating "Grasshopper hasn't processed the policy yet"), a
**fresh** TCP connection to Typha's port timed out - not just an inference,
an actual outage. Restoring either one restored the connection. `default`
stays on workers through step 4, and Grasshopper itself is the only thing
that takes it off, right after it creates its own Typha policy and processes
whatever else already existed when it started (step 5).

### BGP (179) requires Calico Route Reflector mode

Every other port here is master↔worker only because that's genuinely all
that's needed - but Calico's *default* BGP topology is a full node-to-node
mesh (`nodeToNodeMeshEnabled: true`, the default whenever no
`BGPConfiguration` exists), which needs 179 open between **every** node pair,
not just master↔worker. This script does not provide that - confirmed live,
running it under the default mesh left Felix/BIRD unable to establish most
of its peer sessions once `default` was detached.

Instead, this branch assumes Calico is configured for **Route Reflector**
mode with the control-plane node as the (sole) reflector:

```bash
kubectl label node <control-plane-node> route-reflector=true
kubectl annotate node <control-plane-node> projectcalico.org/RouteReflectorClusterID=224.0.0.1
```

```yaml
apiVersion: projectcalico.org/v3
kind: BGPConfiguration
metadata:
  name: default
spec:
  nodeToNodeMeshEnabled: false
---
apiVersion: projectcalico.org/v3
kind: BGPPeer
metadata:
  name: nodes-to-rr
spec:
  nodeSelector: route-reflector != 'true'
  peerSelector: route-reflector == 'true'
```

Under that topology every node's only BGP peer is the control-plane node, so
the master↔worker-only rule shape already used for every other port is
correct here too - no worker↔worker rule exists anywhere in this file, and
none is needed. If your cluster is (or needs to stay) in the default
full-mesh mode instead, 179 needs to be open between every node pair, which
this bootstrap script does not set up.

### Typha network policies

Typha needing a way to receive traffic from Felix on every node isn't
something specific to your application - it's baseline Calico plumbing
Grasshopper itself depends on, so nobody should have to remember to set it
up by hand. On startup, Grasshopper:

1. Finds Typha live (searches for the well-known `k8s-app=calico-typha`
   label cluster-wide - no hardcoded namespace, since that varies by Calico
   install method) and creates its own ingress NetworkPolicy for it if one
   doesn't already exist, using one `/32` `ipBlock` peer per node IP it has
   already discovered - consistent with "no CIDR/subnet configuration
   anywhere" (see below), not a guessed supernet.
2. Processes every NetworkPolicy that now exists (the one it just created,
   plus anything else already applied).
3. Detaches `default` from every worker.

Check its logs to confirm all three happened (`ensure_typha_networkpolicy:
created ...`, then `handle_new_policy`/`Handler ... succeeded` for each
policy, then `detach_defaultSG` running) before treating the cluster as done.

If your Calico install needs some *other* bootstrap-critical NetworkPolicy
beyond Typha's, apply it before this step, not after - a policy applied after
Grasshopper has already started and detached is still handled fine
day-to-day (its `@kopf.on.create` handler fires normally, same as any live
policy change), but it means a window where that traffic isn't open yet -
fine for a regular policy, not for something bootstrap-critical.

## Set the encapsulation toggle

There's exactly one feature toggle, set via CLI args in the Pod/Deployment
spec (`args:` under the `grasshopper` container):

```yaml
args: ["--mode", "PNS", "--intra-project-encapsulation", "vxlan", "--vxlan-port", "4789"]
```

- `--intra-project-encapsulation` is `native` (default) or `vxlan`. This is
  about **same-project** connections only: does Calico use plain native
  routing between nodes in the *same* OpenStack project, or does it
  VXLAN-encapsulate even that traffic? Check your Calico install:
  ```bash
  kubectl get installation default -o yaml | grep encapsulation
  ```
  If it says `VXLAN`, set the toggle to `vxlan`. If it says `None` (native
  routing), leave the default.
- `--vxlan-port` (default `4789`, Calico's own default) only matters if
  you've customized Calico's VXLAN port, or if you have any cross-project
  connections at all (see below).
- **Cross-project connections are not a toggle** - they always require VXLAN
  encapsulation, unconditionally, regardless of this setting. There's no
  "native routing across two different OpenStack projects" option; it isn't
  achievable at the OpenStack network layer (see the design notes at the
  bottom for why).

    
## Deploying the Grasshopper pod

1) Give the grasshopper pod the necessary rights inside the cluster, by executing the command: 
    > kubectl apply -f Deployment/rbac/grasshopper-rbac.yaml

2) Start the Grasshopper Pod by executing the following command:
    > kubectl apply -f Deployment/pods/grasshopper-operator-PNS.yaml

   This starts the grasshopper operator pod (in PNS mode by default).

   If you want to change modes (PNS/PLS), change the args field in the pod yaml file
   to ["--mode", "PLS"] or ["--mode", "PNS"]


