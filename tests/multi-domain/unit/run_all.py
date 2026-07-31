"""
Runs every verify_*.py in this directory in its own subprocess (so one
script's stubbed-module/env-var state can never leak into another) and prints
a pass/fail summary.

Run with: python run_all.py
"""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
scripts = sorted(
    p for p in glob.glob(os.path.join(HERE, "verify_*.py"))
)

results = []
for script in scripts:
    name = os.path.basename(script)
    print(f"\n{'=' * 60}\nRunning {name}\n{'=' * 60}")
    proc = subprocess.run([sys.executable, script], cwd=HERE)
    results.append((name, proc.returncode == 0))

print(f"\n{'=' * 60}\nSUMMARY\n{'=' * 60}")
for name, ok in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")

sys.exit(0 if all(ok for _, ok in results) else 1)
