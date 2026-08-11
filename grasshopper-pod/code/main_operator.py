import kopf
import argparse
import json
import os
from cluster_state import ClusterState
from openstackfiles.create_sg_per_node import create_sg_per_node
from openstackfiles.detach_defaultSG import detach_defaultSG
from security_group_module import SecurityGroupModulePNS
from kubernetes import client, config
from operator_code.watcher_operator import Watcher
from watchdog import WatchDog
import network_mode
import logging
import time
import pandas as pd
import csv
import threading


MODE = None
watcher = None
watchdog = None

# kopf settings.
MAX_WORKERS = 20
DELAY = 2

# Throttling handlers (remove_policy)
WAIT_TIME = 2
last_run_time = 0
remove_handler_lock = threading.Lock()

# ============================================================
# TEST-ONLY instrumentation for a scalability comparison test (experimental-gh
# vs segmentation-aware-gh throughput/failure rate under a pod burst) - lives
# ONLY on this throwaway *-scaletest branch, never merged into the real
# feature branches. Strict no-op unless GH_TEST_ANNOTATE_PROCESSED=1 is set,
# so normal Grasshopper operation (this env var unset) is byte-for-byte
# unaffected. Do not upstream this block.
# ============================================================
GH_TEST_ANNOTATE_PROCESSED = os.environ.get("GH_TEST_ANNOTATE_PROCESSED") == "1"
TEST_PROCESSED_ANNOTATION = "grasshopper.io/test-processed"


def mark_pod_processed_for_test(namespace: str, name: str):
    """
    Adds a throwaway annotation to a pod once it's been successfully handled,
    so an external test harness can measure processing throughput/failures
    (annotation missing after the test window = never processed). Called
    only after the real handling call already returned without raising -
    an exception there propagates normally and this is simply never reached,
    so "annotated" here really does mean "successfully processed."
    """
    if not GH_TEST_ANNOTATE_PROCESSED:
        return
    try:
        client.CoreV1Api().patch_namespaced_pod(
            name, namespace, {"metadata": {"annotations": {TEST_PROCESSED_ANNOTATION: "true"}}}
        )
    except Exception as e:
        print(f"Test instrumentation: failed to annotate pod {name} (ns {namespace}) as processed: {e}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

logger = logging.getLogger(__file__)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['PNS', 'PLS'], required=True)
    parser.add_argument(
        '--intra-project-encapsulation',
        choices=[network_mode.ENCAPSULATION_NATIVE, network_mode.ENCAPSULATION_VXLAN],
        default=network_mode.ENCAPSULATION_NATIVE,
        help="Whether same-OpenStack-project connections are native-routed (default) "
             "or also VXLAN-encapsulated by Calico. Cross-project connections always "
             "require VXLAN regardless of this setting - only relevant to PNS mode.",
    )
    parser.add_argument(
        '--vxlan-port', type=int, default=network_mode.vxlan_port,
        help="VXLAN encapsulation UDP port (Calico's default is 4789).",
    )
    parser.add_argument(
        '--reconcile-interval-seconds', type=int, default=60,
        help="How often the batch reconciliation loop re-syncs pods and the "
             "NodeSegmentationPolicy CR against the event-driven handlers' "
             "state, catching anything they missed. 0 disables it.",
    )
    return parser.parse_args()

def initialize_cluster_configuration():
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
        config.load_incluster_config()
    else:
        config.load_kube_config()

TYPHA_POLICY_NAME = "grasshopper-typha-ingress"


def ensure_typha_networkpolicy():
    """
    Creates the NetworkPolicy that lets Felix (calico-node, on every node)
    reach Typha (which can land on any node) on port 5473 - if nobody else
    has, nobody else will. This isn't a user's application policy; it's
    baseline Calico plumbing this operator itself depends on (workerSG's
    static rules only cover the egress side - see create_master_and_workerSG.py
    - the ingress side only exists once this policy is processed), so
    Grasshopper creates it itself rather than assuming an administrator
    remembered to.

    Discovers Typha's actual namespace/labels live (no hardcoded
    "calico-system", since that varies by install method) by searching for
    the well-known k8s-app=calico-typha label cluster-wide. If no Typha pod
    is found at all (e.g. this cluster doesn't run Typha), skips - nothing to
    protect. Idempotent: does nothing if a policy with this name already
    exists in that namespace, so a pod restart never creates a duplicate.

    Uses one /32 ipBlock peer per currently-known node IP rather than a
    hardcoded subnet - consistent with "no CIDR/subnet configuration
    anywhere" elsewhere in this operator (see README_v2.md); it only ever
    uses node IPs it has already discovered live from the Kubernetes API.
    """
    core = client.CoreV1Api()
    typha_pods = core.list_pod_for_all_namespaces(label_selector="k8s-app=calico-typha").items
    if not typha_pods:
        print("ensure_typha_networkpolicy: no calico-typha pod found, skipping.")
        return

    namespace = typha_pods[0].metadata.namespace
    net = client.NetworkingV1Api()
    existing = net.list_namespaced_network_policy(namespace, field_selector=f"metadata.name={TYPHA_POLICY_NAME}").items
    if existing:
        print(f"ensure_typha_networkpolicy: {namespace}/{TYPHA_POLICY_NAME} already exists, skipping.")
        return

    node_ips = sorted({node.internal_ip for node in ClusterState.get_nodes() if node.internal_ip})
    if not node_ips:
        print("ensure_typha_networkpolicy: no node IPs known yet, skipping.")
        return

    policy = client.V1NetworkPolicy(
        metadata=client.V1ObjectMeta(name=TYPHA_POLICY_NAME, namespace=namespace),
        spec=client.V1NetworkPolicySpec(
            pod_selector=client.V1LabelSelector(match_labels={"k8s-app": "calico-typha"}),
            policy_types=["Ingress"],
            ingress=[client.V1NetworkPolicyIngressRule(
                _from=[client.V1NetworkPolicyPeer(ip_block=client.V1IPBlock(cidr=f"{ip}/32"))
                       for ip in node_ips],
                ports=[client.V1NetworkPolicyPort(protocol="TCP", port=5473)],
            )],
        ),
    )
    net.create_namespaced_network_policy(namespace, policy)
    print(f"ensure_typha_networkpolicy: created {namespace}/{TYPHA_POLICY_NAME} for {len(node_ips)} node IP(s).")


def process_existing_network_policies():
    """
    Synchronously processes every NetworkPolicy that already exists at pod
    startup, so that by the time detach_defaultSG() runs (right after this,
    still inside startup()) every policy the operator needs to have reacted
    to (e.g. a Typha ipBlock policy - see README_v2.md) already has its
    dynamic per-node rule created. Reprocessing the same policy later via the
    @kopf.on.resume handler below is harmless - WatchDog.handle_new_policy
    already no-ops if the policy is already in ClusterState.

    Uses the raw, unparsed API response (_preload_content=False) rather than
    the typed client's .to_dict(): the typed client's dict form uses
    snake_case field names (pod_selector, not podSelector), which
    create_policy_from_policy_dict - written for kopf's raw camelCase JSON
    body - wouldn't recognize.
    """
    resp = client.NetworkingV1Api().list_network_policy_for_all_namespaces(_preload_content=False)
    for item in json.loads(resp.read())["items"]:
        policy = Watcher.create_policy_from_policy_dict(item)
        watchdog.handle_new_policy(policy)

def startup():
    global MODE, watcher, watchdog
    args = parse_args()
    MODE = args.mode
    network_mode.configure(args.intra_project_encapsulation, args.vxlan_port)

    print(f"🚀 Starting Kopf operator in mode: {MODE}, watching all namespaces. "
          f"intra-project encapsulation: {network_mode.intra_project_encapsulation}.")

    # Each OpenStackClient is now created lazily per-project (via for_project())
    # by whatever code first needs that project's Neutron/Nova session - no
    # eager single "default" warm-up here, since assuming a "default" project
    # always exists is exactly what multi-domain support removes.

    # Initializing cluster configuration.
    initialize_cluster_configuration()

    # Initializing Cluster State.
    ClusterState().initialize_light(PNS_scenario=(MODE == "PNS"))

    # If mode is PNS, create a sg for every node.
    if MODE == "PNS":
        create_sg_per_node(delete_existing_rules=True)
        # initialize_light() (above) already listed existing SGs into
        # ClusterState, but create_sg_per_node() may have just created brand
        # new ones (e.g. first run against a fresh node) - re-list so every
        # per-node SG is registered before any policy/pod event tries to look
        # it up via SecurityGroupModulePNS.SGn(), which would otherwise return
        # None for a freshly-created node's SG.
        ClusterState.initialize_security_groups(PNS_scenario=True)

    # Create Watcher.
    watcher = Watcher(PNS_scenario=(MODE == "PNS"))
    watchdog = WatchDog(PNS_scenario=(MODE == "PNS"))

    if MODE == "PNS":
        # Grasshopper depends on Typha being reachable just as much as any
        # user workload does - create that policy itself rather than assume
        # an administrator remembered to (nobody else will).
        ensure_typha_networkpolicy()

        # Process every already-existing NetworkPolicy (including the one
        # just created above) before detaching "default" from workers -
        # detaching any earlier leaves a real ingress gap for whatever
        # traffic those policies were supposed to open (confirmed live -
        # see README_v2.md).
        process_existing_network_policies()
        detach_defaultSG()

    # Batch reconciliation is complementary to, not a replacement for, every
    # event-driven handler above - mode-agnostic (pod tracking matters in PLS
    # too), so this runs regardless of MODE. args.reconcile_interval_seconds
    # of 0 disables it entirely (e.g. for a test run that wants a completely
    # quiet log).
    if args.reconcile_interval_seconds > 0:
        threading.Thread(
            target=reconciliation_loop, args=(args.reconcile_interval_seconds,), daemon=True
        ).start()
        print(f"Batch reconciliation loop started, interval {args.reconcile_interval_seconds}s.")

@kopf.on.startup()
def startup_handler(settings: kopf.OperatorSettings, **kwargs):
    settings.execution.max_workers = MAX_WORKERS
    settings.posting.backoff = DELAY
    logger.info(f"Starting Operator with {MAX_WORKERS} workers.")
    startup()

# Handler for a worker/master node joining the cluster after Grasshopper has
# already started. Existing-at-startup nodes are already handled once, in
# full, by create_sg_per_node() inside startup() - deliberately no
# @kopf.on.resume here too, that would just redo the same idempotent work a
# second time for every node on every operator restart. PLS mode has no
# per-node SGs (SecurityGroupModulePLS keys SGs by labelset, not by node), so
# this is a no-op outside PNS mode.
@kopf.on.create('v1', 'nodes')
def handle_new_node(name, **kwargs):
    if MODE != "PNS":
        return
    print(f"New node joined the cluster: {name} - creating its per-node SG.")
    create_sg_per_node()

NSP_GROUP = "nodesegmentationpolicy.diktyo.x-k8s.io"
NSP_VERSION = "v1alpha1"
NSP_PLURAL = "nodesegmentationpolicies"

CONNECTIVITY_CONFIGMAP_NAME = "grasshopper-connectivity"
CONNECTIVITY_CONFIGMAP_NAMESPACE = "kube-system"


def _node_isolated(node_segments: dict, isolated: bool, n: str, m: str) -> bool:
    if not isolated:
        return False
    n_seg, m_seg = node_segments.get(n), node_segments.get(m)
    return n_seg is not None and m_seg is not None and n_seg != m_seg


def newly_isolated_pairs(old_segments: dict, old_isolated: bool, new_segments: dict, new_isolated: bool) -> set:
    """
    Every unordered node pair that's isolated under the NEW mapping but
    wasn't under the OLD one - i.e. connectivity a segmentation change just
    revoked. Only considers nodes named in either mapping - a pair neither
    mapping ever mentions can't have changed status.
    """
    candidate_nodes = set(old_segments) | set(new_segments)
    pairs = set()
    for n in candidate_nodes:
        for m in candidate_nodes:
            if n >= m:
                continue
            if _node_isolated(new_segments, new_isolated, n, m) and not _node_isolated(old_segments, old_isolated, n, m):
                pairs.add((n, m))
    return pairs


def connectivity_configmap_data(node_segments: dict, isolated: bool) -> dict:
    """
    One grasshopper.connection.boolean.origin.<n>.destination.<m> key per
    ordered pair of nodes named in the current segmentation - mirrors the key
    shape of Nestor-paper's netperf-metrics ConfigMap convention
    (netperf.p90.latency.milliseconds.origin.<n>.destination.<m>). Value "1"
    means allowed, "0" means blocked by segmentation. "Basics" scope only:
    this publishes isolated(n,m), not the full Default/LeastPriv/Channels
    range from isolation.tex. Empty (no keys) whenever isolation isn't
    active - there's nothing segmentation-related to report.
    """
    if not isolated:
        return {}
    node_names = sorted(node_segments)
    data = {}
    for n in node_names:
        for m in node_names:
            if n == m:
                continue
            allowed = "0" if node_segments[n] != node_segments[m] else "1"
            data[f"grasshopper.connection.boolean.origin.{n}.destination.{m}"] = allowed
    return data


def publish_connectivity_configmap(node_segments: dict, isolated: bool):
    v1 = client.CoreV1Api()
    body = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(name=CONNECTIVITY_CONFIGMAP_NAME, namespace=CONNECTIVITY_CONFIGMAP_NAMESPACE),
        data=connectivity_configmap_data(node_segments, isolated),
    )
    try:
        v1.replace_namespaced_config_map(CONNECTIVITY_CONFIGMAP_NAME, CONNECTIVITY_CONFIGMAP_NAMESPACE, body)
    except client.exceptions.ApiException as e:
        if e.status == 404:
            v1.create_namespaced_config_map(CONNECTIVITY_CONFIGMAP_NAMESPACE, body)
        else:
            raise


def sync_node_segments_from_nsp(body: dict):
    """
    Recomputes the node -> segment mapping from the single
    NodeSegmentationPolicy CR's current spec/status - see isolated(n,m) in
    Nestor-paper/formalization/isolation.tex. "Basics" scope only: this
    captures just the isolated(n,m) predicate (blocked vs not), not the full
    Conn(n,m) range (Default/LeastPriv/Channels are a later increment).

    A segmentation change doesn't just gate FUTURE SG_add_conn calls (see
    ClusterState.is_isolated()'s use there) - any rule already created
    between a pair that just became isolated must be actively revoked, since
    it was granted under a connectivity matrix that no longer holds.
    """
    old_isolated = ClusterState().segmentation_isolated
    old_segments = dict(ClusterState().node_segments)

    spec = body.get("spec", {}) or {}
    status = body.get("status", {}) or {}

    if not spec.get("isolated"):
        new_segments, new_isolated = {}, False
        print("NodeSegmentationPolicy: isolation not enabled (spec.isolated is not true) - no node pairs blocked.")
    else:
        new_segments = {}
        for seg in (status.get("segments") or []):
            seg_name = seg.get("name")
            for node_name in (seg.get("nodes") or []):
                new_segments[node_name] = seg_name
        new_isolated = True
        segment_count = len(set(new_segments.values()))
        print(f"NodeSegmentationPolicy: isolation active, {len(new_segments)} node(s) across {segment_count} segment(s).")

    ClusterState.set_node_segments(new_segments, isolated=new_isolated)

    if MODE == "PNS":
        pairs = newly_isolated_pairs(old_segments, old_isolated, new_segments, new_isolated)
        if pairs:
            print(f"NodeSegmentationPolicy: {len(pairs)} node pair(s) newly isolated - revoking any existing rule between them.")
            SecurityGroupModulePNS.revoke_rules_for_isolated_pairs(pairs)

    try:
        publish_connectivity_configmap(new_segments, new_isolated)
    except Exception as e:
        print(f"NodeSegmentationPolicy: failed to publish {CONNECTIVITY_CONFIGMAP_NAME} ConfigMap: {e}")


# ============================================================
# Batch reconciliation loop - a timing-based safety net that runs alongside
# (never instead of) the event-driven kopf handlers above. Those handlers
# react immediately to individual pod/policy/CR events, which is strictly
# better when they fire - this loop exists for when they don't: a handler
# that raised past its retries, a watch stream gap, or a delete event for
# the NodeSegmentationPolicy CR that never arrived. It periodically re-lists
# the cluster's actual current state and replays the SAME handler functions
# the event path uses (handle_new_pod/handle_removed_pod, sync_node_segments_
# from_nsp) for anything that's drifted - it does not duplicate their logic.
# ============================================================

def reconcile_segmentation_once():
    """
    Re-reads the single NodeSegmentationPolicy CR (if any) and re-syncs
    ClusterState through the exact same sync_node_segments_from_nsp() the
    on.field/on.resume handlers use - a missed update self-heals on the next
    tick. Also handles a missed DELETE: if the CR is gone but ClusterState
    still thinks isolation is active, clears it exactly like
    handle_node_segmentation_policy_deleted() does.
    """
    try:
        items = client.CustomObjectsApi().list_cluster_custom_object(NSP_GROUP, NSP_VERSION, NSP_PLURAL).get("items", [])
    except Exception as e:
        print(f"Reconcile: failed to list NodeSegmentationPolicy: {e}")
        return

    if items:
        sync_node_segments_from_nsp(items[0])
    elif ClusterState().segmentation_isolated:
        print("Reconcile: NodeSegmentationPolicy CR no longer exists (missed delete event?) - clearing segmentation.")
        ClusterState.clear_node_segments()
        try:
            publish_connectivity_configmap({}, False)
        except Exception as e:
            print(f"Reconcile: failed to clear {CONNECTIVITY_CONFIGMAP_NAME} ConfigMap: {e}")


def reconcile_pods_once():
    """
    Batch-reconciles ClusterState's tracked pods against the cluster's actual
    current pods in one pass: any pod that exists but isn't tracked (a missed
    create/field event) is handled as new; any tracked pod that no longer
    exists (a missed delete event) is handled as removed. Both go through the
    real WatchDog methods the event handlers use - already idempotent (see
    their own "already handled"/"does not exist" guards), so this is safe to
    run even when nothing has actually drifted. Pods not yet scheduled
    (spec.nodeName unset) are skipped - the spec.nodeName field handler picks
    those up once they are, same as it always does.
    """
    try:
        pod_list = client.CoreV1Api().list_pod_for_all_namespaces().items
    except Exception as e:
        print(f"Reconcile: failed to list pods: {e}")
        return 0, 0

    actual = {}
    for p in pod_list:
        node_name = p.spec.node_name
        if not node_name:
            continue
        pod_dict = {
            "metadata": {"name": p.metadata.name, "namespace": p.metadata.namespace, "labels": p.metadata.labels or {}},
            "spec": {"nodeName": node_name},
        }
        actual[(p.metadata.namespace, p.metadata.name)] = Watcher.create_pod_from_pod_dict(pod_dict)

    known = {(pod.namespace, pod.name): pod for pod in ClusterState.get_pods()}

    new_keys = set(actual) - set(known)
    removed_keys = set(known) - set(actual)

    for namespace, name in new_keys:
        print(f"Reconcile: found untracked pod {name} (ns {namespace}) - handling as new.")
        watchdog.handle_new_pod(actual[(namespace, name)])
        mark_pod_processed_for_test(namespace, name)
    for namespace, name in removed_keys:
        print(f"Reconcile: tracked pod {name} (ns {namespace}) no longer exists - handling as removed.")
        watchdog.handle_removed_pod(known[(namespace, name)])

    return len(new_keys), len(removed_keys)


def reconcile_once():
    reconcile_segmentation_once()
    new_count, removed_count = reconcile_pods_once()
    if new_count or removed_count:
        print(f"Reconcile: batch pass processed {new_count} untracked and {removed_count} stale pod(s).")


def reconciliation_loop(interval_seconds: int):
    while True:
        time.sleep(interval_seconds)
        try:
            reconcile_once()
        except Exception as e:
            print(f"Reconcile: unexpected error during batch reconciliation: {e}")


# Handlers for the single, cluster-scoped NodeSegmentationPolicy CR (see
# Nestor-paper/formalization/isolation.tex and class-scheduling-operator/crds/
# nodesegmentationpolicy-crd.yaml - "we assume that only one such object
# exists in the cluster", matching this CRD's own cluster scope).
#
# on.field (not on.update) on spec.isolated/status.segments specifically -
# not the whole object - so this only recomputes when something that
# actually changes the connectivity matrix changes, not on every reconcile
# tick (status.lastReconcileTime updates every reconcile even when segments
# haven't). on.resume picks up whatever state already exists when Grasshopper
# itself (re)starts - on.field alone never fires for that, same reason
# pods/policies/namespaces elsewhere in this file each need their own
# on.resume handler too.
#
# Rule revocation inside sync_node_segments_from_nsp is gated to MODE ==
# "PNS" (PLS has no per-node SGs), but the ConfigMap publish and the
# ClusterState cache itself are not - they're mode-agnostic bookkeeping.
@kopf.on.resume(NSP_GROUP, NSP_VERSION, NSP_PLURAL)
@kopf.on.field(NSP_GROUP, NSP_VERSION, NSP_PLURAL, field='spec.isolated')
@kopf.on.field(NSP_GROUP, NSP_VERSION, NSP_PLURAL, field='status.segments')
def handle_node_segmentation_policy(body, **kwargs):
    sync_node_segments_from_nsp(body)


# KNOWN LIMITATION (both here and in sync_node_segments_from_nsp above): when
# isolation is lifted - this delete, or a later update with spec.isolated:
# false, or a segment merge - previously-blocked pairs become allowed again,
# but no rule is created for them retroactively. revoke_rules_for_isolated_
# pairs() only ever removes rules for pairs that just became isolated; there
# is no symmetric "re-evaluate every existing policy for pairs that just
# became UN-isolated" step. Until a pod/policy event naturally re-triggers
# SG_add_conn for that pair, connectivity that should now be allowed stays
# missing. Reprocessing all existing policies (like process_existing_
# network_policies() does at startup) would close this gap but is a
# materially bigger change than "the basics" scope covers here.
@kopf.on.delete(NSP_GROUP, NSP_VERSION, NSP_PLURAL)
def handle_node_segmentation_policy_deleted(**kwargs):
    print("NodeSegmentationPolicy deleted - clearing node segmentation, no pairs blocked.")
    ClusterState.clear_node_segments()
    try:
        publish_connectivity_configmap({}, False)
    except Exception as e:
        print(f"NodeSegmentationPolicy: failed to clear {CONNECTIVITY_CONFIGMAP_NAME} ConfigMap: {e}")

@kopf.on.resume('v1', 'pods')
def handle_existing_pod(body, name, namespace, **kwargs):
    node = body.get("spec", {}).get("nodeName")
    if node:
        pod_name = body.get('metadata', {}).get('name')
        print(f"Handling existing pod {pod_name}, scheduled on node {node}.")

        # Reconstruct pod object and pass to handler
        pod_object = Watcher.create_pod_from_pod_dict(body)
        print(f"Handling already existing pod object: {pod_object}")
        watchdog.handle_new_pod(pod_object)


# Handler for when a pod gets scheduled on a node. (handler specifically looks for changes in the spec.nodeName field)
@kopf.on.field('v1', 'pods', field='spec.nodeName')
def handle_new_pod(old, new, body, name, namespace, **kwargs):
    old_node = old
    new_node = new
    pod_name = body.get('metadata').get('name')
    node = body.get("spec").get("nodeName")
   
   # Printing handler being called.
    print(f"New pod {pod_name}! old_node = {old_node}, new_node = {new_node}.")

    # Actually handling the new pod event (that is actually scheduled on a node)
    pod_object = Watcher.create_pod_from_pod_dict(body)
    print(f"Handling the new pod object: {pod_object}")
    watchdog.handle_new_pod(pod_object)
    mark_pod_processed_for_test(namespace, pod_name)

@kopf.on.delete('v1', 'pods')
def handle_removed_pod(body, **kwargs):
    pod_object = Watcher.create_pod_from_pod_dict(body)
    pod_name = pod_object.name
    print(f"Removing pod {pod_name}")
    watchdog.handle_removed_pod(pod_object)

@kopf.on.resume('v1', 'namespaces')
@kopf.on.create('v1', 'namespaces')
@kopf.on.update('v1', 'namespaces')
def handle_new_or_updated_namespace(body, **kwargs):
    name, labels = Watcher.create_namespace_from_dict(body)
    print(f"Registering namespace {name} with labels {labels}")
    watchdog.handle_new_namespace(name, labels)

@kopf.on.delete('v1', 'namespaces')
def handle_removed_namespace(body, **kwargs):
    name, _ = Watcher.create_namespace_from_dict(body)
    print(f"Removing namespace {name}")
    watchdog.handle_removed_namespace(name)

@kopf.on.resume('networking.k8s.io', 'v1', 'networkpolicies')
@kopf.on.create('networking.k8s.io', 'v1', 'networkpolicies')
def handle_new_policy(body, **kwargs):
    policy = Watcher.create_policy_from_policy_dict(body)
    watchdog.handle_new_policy(policy)

@kopf.on.delete('networking.k8s.io', 'v1', 'networkpolicies', retries=5)
def handle_removed_policy(body, **kwargs):
    global last_run_time

    with remove_handler_lock:
        now = time.time()
        time_since_last = now - last_run_time

        if time_since_last < WAIT_TIME:
            delay = WAIT_TIME - time_since_last
            print(f"⏳ Waiting {delay:.1f}s before running handler for handle_removed_policy")
            time.sleep(delay)  # block this thread, allow others

        last_run_time = time.time()
        print(f"✅ Running handler for {handle_removed_policy} at {time.strftime('%X')}")

        try: 
            policy = Watcher.create_policy_from_policy_dict(body)
            watchdog.handle_removed_policy(policy)
        except Exception as e:
            raise kopf.TemporaryError(f"There was a problem removing the policy {policy.name} \n {e}", delay=2)

@kopf.on.cleanup()
def show_cluster_state(**kwargs):
    print(ClusterState())

if __name__ == "__main__":
    kopf.run(
        standalone=True,          # Optional: disables multiprocessing
        clusterwide=True,         # Watch all namespaces, not just one.
    )



