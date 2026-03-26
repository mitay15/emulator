# tools/validate_all.py
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).parent.parent
SUMMARY = ROOT / "data" / "reports" / "compare" / "summary.json"
CACHE = ROOT / "data" / "cache"


def run_compare_runner():
    print("\n=== RUN compare_runner ===")
    cmd = "python -m aaps_emulator.runner.compare_runner --report --fast"
    proc = subprocess.run(cmd, shell=True)
    if proc.returncode != 0:
        print("compare_runner FAILED")
        sys.exit(1)


def load_summary():
    if not SUMMARY.exists():
        print("summary.json not found!")
        sys.exit(1)
    with open(SUMMARY, "r", encoding="utf-8") as f:
        return json.load(f)


def check_summary(summary):
    mism = summary["mismatches"]
    total = summary["total_blocks"]

    print("\n=== SUMMARY CHECK ===")
    print(f"Total blocks: {total}")

    errors = {k: v for k, v in mism.items() if v > 0}

    if not errors:
        print("[OK] No mismatches in summary.json")
        return True

    print("[FAIL] Mismatches found:")
    for k, v in errors.items():
        print(f" - {k}: {v}")

    return False


def check_predbg_details(summary):
    print("\n=== CHECK predBG DETAILS ===")

    bad = []
    for r in summary["results"]:
        if r.get("predBGs_max_diff", 0) > 0:
            bad.append(r["idx"])

    if not bad:
        print("[OK] predBG curves fully match")
        return True

    print(f"[FAIL] predBG mismatch in blocks: {bad[:10]}{'...' if len(bad)>10 else ''}")
    return False


def check_inputs():
    print("\n=== CHECK INPUTS ===")

    missing = []
    for f in sorted(CACHE.glob("mismatch_block_*.json")):
        idx = int(f.stem.split("_")[-1])
        inp = CACHE / f"inputs_before_algo_block_{idx}.json"
        if not inp.exists():
            missing.append(idx)

    if not missing:
        print("[OK] All inputs_before_algo_block_* exist")
        return True

    print(f"[FAIL] Missing inputs for blocks: {missing[:10]}")
    return False


def main():
    run_compare_runner()
    summary = load_summary()

    ok1 = check_summary(summary)
    ok2 = check_predbg_details(summary)
    ok3 = check_inputs()

    print("\n=== FINAL RESULT ===")
    if ok1 and ok2 and ok3:
        print("[OK] Python emulator FULLY MATCHES AAPS")
        sys.exit(0)
    else:
        print("[FAIL] Differences detected")
        sys.exit(1)


if __name__ == "__main__":
    main()
