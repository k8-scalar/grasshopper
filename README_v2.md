# Grasshopper: Multi-domain (multi-OpenStack-project) getting started

This is a supplement to the main [README.md](README.md), specific to the
`multi-domain-grasshopper` branch. It covers what's different when your
Kubernetes cluster's nodes span **more than one OpenStack project** (each with
its own credentials), instead of the single-project setup the main README
assumes.

If your cluster is single-project, none of this applies - everything here is
additive and off by default.

**Tests**: see [`tests/multi-domain/`](tests/multi-domain/README.md) -
`tests/multi-domain/unit/` runs anywhere with no cluster needed,
`tests/multi-domain/cluster/` is the manual runbook for validating against a
real 2-project cluster.

## Scope

Multi-domain support only exists for **PNS mode** (`--mode PNS`). PLS mode's
per-labelset security-group model doesn't decompose cleanly across projects
(a labelset's matching pods can span many nodes in many projects with no
single stable remote target) and is unaffected by anything below.

## 1. Label your nodes by OpenStack project

Grasshopper needs to know which OpenStack project each Kubernetes node
belongs to. It reads this from a node label - nothing else. There is no
separate "project topology" config file.

```bash
kubectl label node <node-name> grasshopper.io/openstack-project=<project-id>
```

Use whatever string you like as `<project-id>`, as long as it matches the
`"key"` you give that project's credentials in `OS_PROJECTS_JSON` (see below).
In practice, using the OpenStack project ID itself (`openstack token issue -f
value -c project_id`) is a good choice, since it's already unique and you
already have it on hand.

**Any node without this label is treated as belonging to the `"default"`
project.** This is what makes multi-domain support fully backward compatible:
an existing single-project deployment has no labels, every node resolves to
`"default"`, and behaves exactly as before.

You can check the current mapping at any time with:

```bash
kubectl get nodes -L grasshopper.io/openstack-project
```

## 2. Provide credentials for each project (without putting secrets in git)

Grasshopper's `OpenStackClient` is a per-project registry. Instead of the
single flat `OS_AUTH_URL` / `OS_APPLICATION_CREDENTIAL_ID` / ... variables the
main README describes, set **one** variable, `OS_PROJECTS_JSON` - a JSON list,
one entry per project:

```json
[
  {
    "key": "<same value as the node label above>",
    "auth_url": "<auth_url from that project's clouds.yaml>",
    "application_credential_id": "<application_credential_id>",
    "application_credential_secret": "<application_credential_secret>",
    "neutron_endpoint": "<Neutron public endpoint - see below>",
    "nova_endpoint": "<Nova public endpoint - see below>"
  },
  {
    "key": "<the other project's key>",
    "...": "..."
  }
]
```

Everything under `auth`/`application_credential_*` comes straight out of that
project's `clouds.yaml` (the file you download from Horizon's "Application
Credentials" page - see `.env.dist` for the exact field mapping). The two
endpoint fields aren't in `clouds.yaml` by default; get them once per project
with:

```bash
openstack --os-cloud <cloud-name> catalog list
```

and take the `public` interface URL for the `neutron` and `nova` services.

**If a project isn't in `OS_PROJECTS_JSON` at all**, and it's specifically the
`"default"` one, Grasshopper falls back to the legacy flat `OS_*` env vars for
it - so you never *need* `OS_PROJECTS_JSON` for a single-project deployment,
and you can still mix "one project via flat vars + others via
`OS_PROJECTS_JSON`" if that's convenient. For any *other* project key, there's
no fallback - it must have its own entry.

### Getting this into the pod without it ever touching git or your shell history

Never put the real JSON on a command line (it'll land in shell history) and
never commit it. Build it in a local file that's `.gitignore`d, then create
the Secret from that file, in the `kube-system` namespace (see below for why):

```bash
# projects.json - keep this OUTSIDE the repo, or make sure it's gitignored.
kubectl create secret generic grasshopper-openstack-creds \
  -n kube-system \
  --from-file=OS_PROJECTS_JSON=./projects.json
```

The Deployment/Pod spec picks it up exactly like the single-project case,
via `envFrom.secretRef` (see `Deployment/pods/grasshopper-operator-PNS.yaml`) -
no manifest changes needed, since it's the same Secret name, just with a
different key populated.

### Where Grasshopper itself runs - control-plane node only

`grasshopper-operator-PNS.yaml` schedules the pod onto the control-plane node
specifically (`nodeSelector: node-role.kubernetes.io/control-plane: ""`, with
a matching `toleration` for the usual control-plane taint), in the
`kube-system` namespace - it is **not** meant to run on an arbitrary worker.

This is deliberate, not incidental: a Kubernetes Secret's data is only ever
fetched and materialized (as env vars, in this case) by the kubelet on
whichever node the pod actually lands on. In a multi-domain cluster, worker
nodes can belong to any of several OpenStack projects, and none of them
should ever see any project's credentials - only the control-plane node
should. Pinning Grasshopper there means `OS_PROJECTS_JSON` is never fetched
by, or visible to, any worker node's kubelet, regardless of which project(s)
it belongs to.

Delete your local `projects.json` once the Secret is created if you don't
need it again - `kubectl get secret ... -o yaml` will show you the (base64,
not encrypted) value again later if you ever need to reconstruct it, but
there's no reason to leave a second copy lying around on disk.

## 3. Set the encapsulation toggle

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

## 4. Run the bootstrap script for baseline cluster connectivity

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

## 5. Deploy Grasshopper

Same as the single-project case (see main README) - build/push the image,
apply `Deployment/rbac/grasshopper-rbac.yaml`, apply your Pod/Deployment spec
with the args from step 3 and the Secret from step 2.

## How Grasshopper learns node IPs and builds CIDRs

There is **no CIDR/subnet configuration anywhere** - you never need to tell
Grasshopper "project A is 172.22.14.0/24". The only thing you configure is
the node→project label from step 1. Everything else is discovered live from
the Kubernetes API:

- At startup (and whenever the node list is (re-)read), Grasshopper reads
  each Node object's `status.addresses` and keeps the one with
  `type == InternalIP` as that node's real IP.
- When it needs to create a rule between two nodes in **different**
  projects, it can't reference the peer's security group directly (Neutron
  doesn't allow a `remote_group_id` across projects), so it builds a plain
  CIDR rule instead: the peer node's own InternalIP with a `/32` mask - e.g.
  `172.22.8.74/32`. Not a subnet, not a project-wide range - just that one
  node's address, matching the same one-connection-at-a-time granularity
  PNS mode already uses for same-project rules.
- Same-project rules never need a CIDR at all - they still reference the
  peer's security group directly, exactly as before.

So "how do the different CIDRs get learned" has a one-line answer: they
aren't - only individual node IPs are, straight from `kubectl get nodes -o
wide`/the Node API objects, refreshed automatically as the node list changes.

## What actually happens on the wire (background)

For a connection between nodes in different projects: routing between two
OpenStack projects' subnets does not preserve a pod's real source IP through
plain native routing, so it requires VXLAN encapsulation - and once VXLAN is
in play, OpenStack's security-group enforcement can only ever see the
*outer* Node-to-Node VXLAN envelope (UDP, port 4789 by default), never the
inner pod-to-pod packet's real port. That's why:

- The rule's target has to be the peer node's real IP (that's what's on the
  outer envelope), never the pod's IP and never a `remote_group_id`.
- The rule's port has to be the VXLAN port, never the NetworkPolicy's actual
  port - because that's genuinely all that's visible at this hop.
- The actual per-pod, per-port enforcement the NetworkPolicy asked for still
  happens - just not at the OpenStack layer for the cross-project leg. Calico
  enforces NetworkPolicies locally via iptables/eBPF on every node regardless
  of any of this; Grasshopper's contribution across a project boundary is a
  coarser, additional lateral-movement barrier ("can this node-pair even
  exchange VXLAN traffic at all"), on top of Calico's own enforcement, not a
  full re-implementation of the policy at that hop.

## Known limitations

- PNS mode only (see Scope above).
- If a node's `grasshopper.io/openstack-project` label changes after
  Grasshopper has already computed rules involving that node, those rules
  are not retroactively recomputed - relabel before the node starts running
  relevant pods, not after.
- Deleting many pods/policies at once (e.g. a whole namespace) is handled
  correctly, but relies on the fix in this branch for a specific pod/policy
  removal ordering bug - make sure you're running a build that includes it
  (commit `09a84c4` or later on this branch).
- The BGP (179) rules assume Calico is running in Route Reflector mode with
  the control-plane node as the reflector - see the note in step 4 above.
  Under Calico's default full node-to-node mesh, this bootstrap script does
  not open the worker↔worker 179 connectivity that mode requires.
