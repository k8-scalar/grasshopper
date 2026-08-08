#!/usr/bin/env bash
# config.sh - cluster-specific settings for the elastic-orchestration tests
# in this directory. Edit these to match your own cluster before running any
# test-*.sh script here. Sourced by lib.sh, not run directly.

export GH_NAMESPACE="${GH_NAMESPACE:-kube-system}"
export GH_POD="${GH_POD:-grasshopper-multidomain-test}"

# Two OpenStack projects, and (at least) two spare worker nodes in EACH -
# nodes not already hosting something you care about (Typha, control-plane,
# etc.), since the tests schedule throwaway pods directly onto them via
# spec.nodeName. Project A must be the one with the control-plane node.
export PROJECT_A_ID="${PROJECT_A_ID:-ffff833f2281486eb39d45761f203e4d}"
export PROJECT_A_NODE_1="${PROJECT_A_NODE_1:-micro-worker-2}"
export PROJECT_A_NODE_2="${PROJECT_A_NODE_2:-micro-worker-4}"
export PROJECT_A_NODE_3="${PROJECT_A_NODE_3:-micro-worker-5}"
export PROJECT_A_NODE_4="${PROJECT_A_NODE_4:-micro-worker-6}"

# Project B is only needed for test-elastic-cross-project.sh - leave the
# defaults if you only have one OpenStack project; that script will just
# fail its kubectl/openstack lookups, which is fine if you don't run it.
export PROJECT_B_ID="${PROJECT_B_ID:-5a1c172825644292a68fd6acee057f86}"
export PROJECT_B_NODE_1="${PROJECT_B_NODE_1:-cloud-worker-2}"
export PROJECT_B_NODE_2="${PROJECT_B_NODE_2:-cloud-worker-3}"
