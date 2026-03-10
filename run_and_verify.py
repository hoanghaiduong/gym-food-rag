#!/usr/bin/env python3
"""
Run collector + verify schema in one go.
"""
import subprocess
import sys

print("=" * 70)
print("STEP 1: Running data collector (MAX_PAGES=57)...")
print("=" * 70)

result = subprocess.run(
    [sys.executable, "-c", 
     "import scripts.data_collector_v2 as s; s.MAX_PAGES=57; s.START_PAGE=1; s.run_collection()"],
    cwd="."
)

if result.returncode != 0:
    print("ERROR: Collector failed")
    sys.exit(1)

print()
print("=" * 70)
print("STEP 2: Verifying schema...")
print("=" * 70)

result = subprocess.run([sys.executable, "verify_schema.py"], cwd=".")
sys.exit(result.returncode)
