# Manual real-cluster test

This is the actual runbook used to validate the multi-domain feature against
a real 2-project OpenStack cluster. Everything here needs a real Kubernetes
cluster whose nodes span (at least) two OpenStack projects, and real
credentials for both - there's no way to run this without one. If you just
want confidence the *logic* is correct without any of that, run the scripts
in `../unit/` instead.

Read [`../../../README_v2.md`](../../../README_v2.md) first for the concepts
(node labeling, credentials, the toggle, how CIDRs are learned) - this file
is just the concrete step-by-step.

## 0. Prerequisites

- `kubectl` pointed at your cluster.
- Docker (or `nerdctl`/anything that can build + push an image) somewhere
  with network access to your image registry.
- OpenStack CLI access (or `clouds.yaml`) for each project involved, so you
  can inspect security groups afterward.
- RBAC already applied: `kubectl apply -f ../../../Deployment/rbac/grasshopper-rbac.yaml`.

## 1. Label your nodes

Pick at least one node in each of two OpenStack projects:

```bash
kubectl label node <node-in-project-A> grasshopper.io/openstack-project=<project-A-id>
kubectl label node <node-in-project-B> grasshopper.io/openstack-project=<project-B-id>
kubectl get nodes -L grasshopper.io/openstack-project   # sanity check
```

## 2. Build and push the image

```bash
cd ../../../grasshopper-pod
docker build -t <your-registry>/grasshopper:multi-domain-test .
docker push <your-registry>/grasshopper:multi-domain-test
```

(If your build environment doesn't have Docker but does have `nerdctl` +
`buildkitd`, that works too - `nerdctl build` is a drop-in replacement.)

## 3. Create the credentials Secret (without ever writing secrets into this repo)

Build a `projects.json` **outside this repo** (or in a path covered by
`.gitignore`) shaped like the example in `.env.dist`'s `OS_PROJECTS_JSON`
section, with a `"key"` per project matching the labels from step 1. Then:

```bash
kubectl create secret generic grasshopper-openstack-creds \
  -n kube-system \
  --from-file=OS_PROJECTS_JSON=./projects.json
```

Never put the JSON directly on a command line - it'll end up in shell
history. `--from-file` keeps the secret's content out of your terminal
entirely. The Secret lives in `kube-system`, the same namespace as the pod -
see the note on node/namespace placement below for why.

## 4. Deploy Grasshopper

`deploy-test-pod.yaml` runs Grasshopper in the `kube-system` namespace,
scheduled onto the control-plane node only (`nodeSelector` +
`tolerations` in the manifest) - **not** an arbitrary worker node. This is
deliberate: a pod's Secret data is only ever fetched/materialized by the
kubelet on whichever node the pod actually lands on, so pinning Grasshopper
to the control-plane node means the `OS_PROJECTS_JSON` credentials are never
present on any worker node's kubelet, regardless of which project(s) those
workers belong to.

Edit `deploy-test-pod.yaml`'s remaining marked fields (your image, the
encapsulation flag if you need it), then:

```bash
kubectl apply -f deploy-test-pod.yaml
kubectl wait --for=condition=Ready pod/grasshopper-multidomain-test -n kube-system --timeout=120s
kubectl logs grasshopper-multidomain-test -n kube-system | grep -iE "error|traceback|Finished checking"
```

You want to see `Finished checking SGs` and nothing under `error`/`traceback`.

**Note on log output**: Python's `print()` is block-buffered when stdout
isn't a terminal (as here, piped through `kubectl logs`), so plain `print()`
diagnostic lines can lag behind what's actually happened by quite a while -
kopf's own `logging`-module status lines (`Handler '...' succeeded`) show up
immediately and are the more reliable thing to check if something looks
like it's "not processing."

## 5. Deploy the test app and verify the rules

Edit `thorough-test-app.yaml`'s three `nodeName` values (two nodes in one
project, one in the other), then:

```bash
kubectl apply -f thorough-test-app.yaml
kubectl wait --for=condition=Ready pod -l app=app-a -n gh-multidomain-thorough --timeout=90s
```

Check the actual OpenStack state directly - this is the real verification,
not the pod's own logs:

```bash
# Same-project pair (frontend<->backend): expect SG-to-SG (remote_group_id),
# port 4789/udp if the vxlan toggle is on, otherwise the real port/protocol.
openstack --os-cloud <project-A-cloud> security group rule list SG_<frontend-node> -f value
openstack --os-cloud <project-A-cloud> security group rule list SG_<backend-node> -f value

# Cross-project pair (backend<->database): expect a CIDR of the OTHER node's
# real IP (a /32), port 4789/udp, on BOTH sides.
openstack --os-cloud <project-B-cloud> security group rule list SG_<database-node> -f value
```

Then confirm actual reachability matches what the NetworkPolicies allow -
`test-connectivity.sh` looks up the three pods' IPs live and checks
frontend->backend and backend->database both succeed, and frontend->database
is blocked:

```bash
./test-connectivity.sh
```

## 6. Verify removal

```bash
kubectl delete namespace gh-multidomain-thorough
kubectl logs grasshopper-multidomain-test -n kube-system --tail=50 | grep -iE "handle_removed"
```

All `handle_removed_pod`/`handle_removed_policy` handlers should say
`succeeded`. Then re-run the same `security group rule list` commands from
step 5 - every rule should now be gone.

## 7. Clean up

```bash
kubectl delete pod grasshopper-multidomain-test -n kube-system
kubectl delete secret grasshopper-openstack-creds -n kube-system
```

Per-node security groups created along the way are harmless to leave (they're
empty once the app they were for is removed), but delete them via the
OpenStack CLI/Horizon if you'd rather not leave them lying around.
