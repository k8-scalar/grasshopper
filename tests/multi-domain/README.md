# Multi-domain Grasshopper tests

Tests specific to the `multi-domain-grasshopper` branch's cross-OpenStack-
project support. See [`README_v2.md`](../../README_v2.md) at the repo root
for the concepts these exercise.

## `unit/` - no cluster needed

Pure-Python scripts. Each stubs out the OpenStack SDK packages
(`keystoneauth1`/`neutronclient`/`novaclient`) and imports the real,
unmodified `grasshopper-pod/code` modules directly, mocking only the actual
Neutron/Nova network calls. No live Kubernetes cluster, no OpenStack project,
nothing to configure - they run anywhere Python 3.10+ is installed.

```bash
cd unit
python run_all.py          # runs every verify_*.py and prints a summary
python verify_multidomain.py   # or run just one
```

What each one covers:

| Script | Covers |
|---|---|
| `verify_multidomain.py` | `OpenStackClient`'s per-project registry (incl. single-project backward compatibility), `rule_from()`'s same-project/vxlan-toggle/cross-project rule-shape table, the CIDR-target fix in `add_rule_to_remotes`, project-aware client resolution |
| `verify_namespace_isolation.py` | The namespace-isolation fix (issue #8) still holds on this branch: same-label-different-namespace, `namespaceSelector`, combined `podSelector`+`namespaceSelector`, namespace-aware conflict/redundancy checks, the `TestPolicies/` fixture set |
| `verify_removal_race_fix.py` | `SG_remove_conn`'s guard across every pod/policy removal ordering (including the exact one that used to leave stale rules), and that a genuinely different policy still correctly blocks removal |
| `verify_master_worker_sg.py` | `create_master_and_workerSG()`: per-project `masterSG`/`workerSG`, same-project `remote_group_id`, cross-project CIDR, no cross-project attach attempts |
| `verify_detach_default_sg.py` | `detach_defaultSG()`: same per-project resolution, no cross-project `nova.servers.find()` |
| `verify_attach_default_sg.py` | `attach_defaultSG()`: same per-project resolution, mirrors `detach_defaultSG()` |
| `verify_setup_gh_ordering.py` | `setup_gh()` attaches `default` before creating masterSG/workerSG, and never detaches it itself |
| `verify_startup_detach_ordering.py` | `main_operator.py`'s `startup()`: ensures the Typha policy, then processes every already-existing NetworkPolicy, then calls `detach_defaultSG()`, in that order (PNS mode only - never detaches in PLS mode) |
| `verify_ensure_typha_networkpolicy.py` | `ensure_typha_networkpolicy()`: skips if no Typha pod found or a policy already exists (idempotent), otherwise creates one in Typha's actual discovered namespace with one `/32` ipBlock peer per known node IP |
| `verify_rule_dedup_across_policies.py` | `Rule`'s hash/eq contract (a fresh id=None rule must hash equal to an already-created same-target-and-traffic rule), and that two independent policies/pods converging on the same CIDR target on one node never both attempt to create the identical OpenStack rule |

## `cluster/` - real OpenStack + Kubernetes cluster required

Deployment manifests plus a step-by-step runbook
([`cluster/README.md`](cluster/README.md)) for validating the feature end to
end against a real cluster whose nodes span two OpenStack projects: deploy
Grasshopper as an actual Pod, deploy a realistic 3-tier app split across both
projects, and verify the exact security-group rules created (and later
removed) directly via the OpenStack CLI. This is what was actually run to
validate this branch before merging any of it.
