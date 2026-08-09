# Elastic orchestration tests - real cluster required

Verifies Grasshopper (PNS mode) dynamically attaches and detaches OpenStack
security-group rules as pods matching a NetworkPolicy scale in and out, for
every kind of NetworkPolicy peer this branch supports - not a static
snapshot computed once at policy-apply time. Each script schedules
throwaway pods directly onto specific nodes via `spec.nodeName`, checks the
*actual* OpenStack rule state (not just Grasshopper's own logs) via
`kubectl exec` into the live Grasshopper pod, and cleans up after itself.

Every script follows the same shape: baseline → scale the target out to a
new node → scale out again on the *same* node (idempotency - no duplicate
rule) → partial scale-in (rule survives while another pod still needs it) →
full scale-in (rule removed, other nodes untouched) → scale the peer side →
full teardown (zero leftover rules anywhere).

## Prerequisites

- `kubectl` pointed at your cluster.
- Grasshopper already deployed in PNS mode (see `../README.md` and the main
  [`README_v2.md`](../../../../README_v2.md)) and healthy.
- Edit [`config.sh`](config.sh) with your own node names and OpenStack
  project id(s) - pick spare worker nodes not already hosting something you
  care about (Typha, control-plane, etc.), since these scripts schedule
  pods directly onto them.

## Running

```bash
./run-all.sh                        # everything, with a final summary
./test-elastic-same-project.sh      # or just one
```

Each script is self-contained and cleans up its own namespace(s) on exit
(including on failure), so they can be run individually or in any order.

## What each script covers

| Script | Peer type | Covers |
|---|---|---|
| `test-elastic-same-project.sh` | `podSelector`, one OpenStack project | `remote_group_id`-based rules; scale in/out on both the selected (target) and peer sides; per-node idempotency and reference counting |
| `test-elastic-cross-project.sh` | `podSelector`, two OpenStack projects | Same scaling behavior, but via CIDR-of-real-node-IP (Neutron disallows cross-tenant `remote_group_id`), always on the VXLAN port regardless of the `--intra-project-encapsulation` toggle |
| `test-elastic-namespaceselector.sh` | `namespaceSelector` | Matching driven by the peer's *namespace* labels, not its own pod labels; a decoy pod with identical pod labels in an unlabeled namespace is correctly excluded; the documented "namespace label changes aren't retroactively recomputed for already-matched pods" limitation in `watchdog.py`, confirmed both ways (existing rule persists, but a *new* pod created after the relabel is evaluated against current state) |
| `test-elastic-ipblock.sh` | `ipBlock` (CIDR) | Architecturally different - a CIDR peer is a static address block, never tracked as a live pod, always uses the literal port (by design - `ipBlock` is assumed to be genuinely external traffic, never VXLAN). No "peer side" to scale; instead tests scaling the selected pods, and reference-counting across multiple *independent* policies that happen to share the same CIDR+port target - the exact scenario that used to trip the `Rule.__hash__`/`__eq__` bug fixed in `classes.py` against a real Neutron backend |

## Files

- `config.sh` - the one file you need to edit per-cluster (node names, project ids).
- `lib.sh` - shared helpers: `check`/`report_and_exit` (pass/fail bookkeeping),
  `sg_rule_count`/`wait_for_rule_count` (query real OpenStack rule state via
  the live Grasshopper pod), `same_project_port`/`vxlan_port` (resolve which
  port a rule should actually use, since that depends on this deployment's
  own `--intra-project-encapsulation` setting - never hardcoded).
- `run-all.sh` - runs every `test-elastic-*.sh` here and prints a summary.
