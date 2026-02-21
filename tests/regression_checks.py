# aaps_emulator/tests/regression_checks.py
"""
Simple regression checks for selected idx values.
Run from inside aaps_emulator:
  python -m tests.regression_checks --ref tests/reference.csv --logs logs
"""

import argparse
import csv

from analysis.compare_runner import run_compare_on_all_logs
from core.autoisf_algorithm import determine_basal_autoisf


def safe_float(s, default=0.0):
    try:
        return float(s)
    except Exception:
        return default


def load_reference(path):
    ref = {}
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for rec in r:
            try:
                idx = int(rec.get("idx"))
            except Exception:
                continue
            ref[idx] = {
                "aaps_eventual": safe_float(rec.get("aaps_eventual")),
                "aaps_rate": safe_float(rec.get("aaps_rate")),
                "aaps_insreq": safe_float(rec.get("aaps_insreq")),
            }
    return ref


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ref", required=True)
    p.add_argument("--logs", default="logs")
    p.add_argument("--check", nargs="*", type=int, help="specific idx to check")
    args = p.parse_args()

    reference = load_reference(args.ref)
    rows, blocks, inputs = run_compare_on_all_logs(args.logs)

    # build mapping idx -> (row, block, input)
    mapping = {}
    for r, b, inp in zip(rows, blocks, inputs):
        mapping[r.get("idx")] = (r, b, inp)

    # default checks: all reference idxs or provided subset
    to_check = args.check if args.check else sorted(reference.keys())

    failures = []
    for idx in to_check:
        if idx not in mapping or idx not in reference:
            continue
        r, b, inp = mapping[idx]
        errs = []
        logs = []
        res = determine_basal_autoisf(
            glucose_status=inp.get("glucose_status"),
            currenttemp=inp.get("current_temp"),
            iob_data_array=inp.get("iob_array"),
            profile=inp.get("profile"),
            autosens_data=inp.get("autosens"),
            meal_data=inp.get("meal"),
            rt=inp.get("rt"),
            auto_isf_consoleError=errs,
            auto_isf_consoleLog=logs,
        )
        ref = reference[idx]
        ev_ok = (
            res.eventualBG is not None
            and abs(res.eventualBG - ref["aaps_eventual"]) <= 0.5
        )
        rate_ok = abs((res.rate or 0.0) - ref["aaps_rate"]) <= 1.0
        ins_ok = abs((res.insulinReq or 0.0) - ref["aaps_insreq"]) <= 0.5
        print(
            f"idx {idx}: ref_ev={ref['aaps_eventual']} py_ev={res.eventualBG} ev_ok={ev_ok} rate_ref={ref['aaps_rate']} py_rate={res.rate} rate_ok={rate_ok} ins_ref={ref['aaps_insreq']} py_ins={res.insulinReq} ins_ok={ins_ok}"
        )
        if not (ev_ok and rate_ok and ins_ok):
            failures.append(idx)

    print("\nRegression summary:")
    print(f"  checked: {len(to_check)}")
    print(f"  failures: {len(failures)}")
    if failures:
        print("  failed idxs:", failures)


if __name__ == "__main__":
    main()
