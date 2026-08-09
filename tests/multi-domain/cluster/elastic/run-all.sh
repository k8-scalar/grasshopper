#!/usr/bin/env bash
# Runs every test-elastic-*.sh in this directory against the real cluster
# kubectl is pointed at, and prints a pass/fail summary. Each script cleans
# up its own namespace(s) even on failure (trap EXIT), so a failed run
# doesn't leave test resources behind for the next one.
#
# Usage: ./run-all.sh
set -uo pipefail   # deliberately NOT -e: one script failing must not stop the rest
cd "$(dirname "${BASH_SOURCE[0]}")"

SCRIPTS=(test-elastic-*.sh)
declare -A RESULTS

for script in "${SCRIPTS[@]}"; do
  echo
  echo "============================================================"
  echo "Running $script"
  echo "============================================================"
  if ./"$script"; then
    RESULTS["$script"]="PASS"
  else
    RESULTS["$script"]="FAIL"
  fi
done

echo
echo "============================================================"
echo "SUMMARY"
echo "============================================================"
overall=0
for script in "${SCRIPTS[@]}"; do
  echo "[${RESULTS[$script]}] $script"
  [ "${RESULTS[$script]}" == "PASS" ] || overall=1
done

exit "$overall"
