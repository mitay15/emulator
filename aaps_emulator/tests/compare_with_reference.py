# aaps_emulator/tests/compare_with_reference.py
"""
Compare python AutoISF outputs with reference CSV.
Usage (from inside aaps_emulator):
  python -m tests.compare_with_reference --ref tests/reference.csv --logs logs
"""

import argparse
import csv
import logging
import math

from analysis.compare_runner import run_compare_on_all_logs
from core.autoisf_algorithm import determine_basal_autoisf

logger = logging.getLogger(__name__)


def safe_float(s, default=0.0):
    if s is None:
        return default
    s = str(s).strip()
    if s == "":
        return default
    try:
        return float(s)
    except Exception:
        try:
            return float(s.replace(",", "."))
        except Exception:
            return default


def safe_int(s, default=0):
    if s is None:
        return default
    s = str(s).strip()
    if s == "":
        return default
    try:
        return int(float(s))
    except Exception:
        return default


def load_reference_csv(path):
    rows = {}
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for rec in r:
            idx_raw = rec.get("idx")
            if idx_raw is None or str(idx_raw).strip() == "":
                continue
            try:
                idx = int(str(idx_raw).strip())
            except Exception:
                logger.exception(
                    "compare_with_reference: skipping row due to exception"
                )
                continue
            rows[idx] = {
                "ts_s": safe_int(rec.get("ts_s"), 0),
                "aaps_eventual": safe_float(rec.get("aaps_eventual"), 0.0),
                "aaps_rate": safe_float(rec.get("aaps_rate"), 0.0),
                "aaps_duration": safe_int(rec.get("aaps_duration"), 0),
                "aaps_insreq": safe_float(rec.get("aaps_insreq"), 0.0),
            }
    return rows


def rmse(errors):
    if not errors:
        return 0.0
    s = sum(e * e for e in errors)
    return math.sqrt(s / len(errors))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ref", required=True)
    p.add_argument("--logs", default="logs")
    args = p.parse_args()

    reference = load_reference_csv(args.ref)
    rows, blocks, inputs = run_compare_on_all_logs(args.logs)

    compared = 0
    within_tol = 0
    ev_errors = []
    rate_errors = []
    ins_errors = []

    for r, _b, inp in zip(rows, blocks, inputs, strict=True):
        idx = r.get("idx")
        ref = reference.get(idx)
        if ref is None:
            continue

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

        py_ev = res.eventualBG if res.eventualBG is not None else None
        py_rate = res.rate if res.rate is not None else 0.0
        py_ins = res.insulinReq if res.insulinReq is not None else 0.0

        ref_ev = ref.get("aaps_eventual")
        ref_rate = ref.get("aaps_rate")
        ref_ins = ref.get("aaps_insreq")

        if ref_ev is None:
            continue

        compared += 1
        try:
            ev_err = (
                float(py_ev) - float(ref_ev)
                if py_ev is not None
                else float(ref_ev) * -1.0
            )
            ev_errors.append(ev_err)
            if abs(ev_err) <= 0.5:
                within_tol += 1
        except Exception:
            logger.exception("compare_with_reference: suppressed exception")

        try:
            rate_err = float(py_rate) - float(ref_rate)
            rate_errors.append(rate_err)
        except Exception:
            logger.exception("compare_with_reference: suppressed exception")

        try:
            ins_err = float(py_ins) - float(ref_ins)
            ins_errors.append(ins_err)
        except Exception:
            logger.exception("compare_with_reference: suppressed exception")

    print("Comparison summary:")
    print(f"  total compared: {compared}")
    print(f"  within tolerance (eventualBG ±0.5 mmol/L): {within_tol}")
    print(f"  RMSE eventualBG: {rmse(ev_errors)}")
    print(f"  RMSE rate: {rmse(rate_errors)}")
    print(f"  RMSE insulinReq: {rmse(ins_errors)}")

    # Top 10 eventualBG errors:
    ev_abs_sorted = sorted(
        enumerate(ev_errors),
        key=lambda x: abs(x[1]),
        reverse=True,
    )[:10]
    print("\nTop 10 eventualBG errors:")
    # we need mapping from enumerate index to actual row idx; rebuild list of compared idxs
    compared_idxs = []
    for r, _b, _inp in zip(rows, blocks, inputs, strict=True):
        idx = r.get("idx")
        if idx is None:
            continue
        if idx in reference:
            compared_idxs.append(idx)
    for _pos, (enum_idx, err) in enumerate(ev_abs_sorted):
        try:
            real_idx = compared_idxs[enum_idx]
            ref_ev = reference.get(real_idx).get("aaps_eventual")
            # recompute py_ev by calling algorithm again for clarity
            inp = None
            for rr, _bb, ii in zip(rows, blocks, inputs, strict=True):
                if rr.get("idx") == real_idx:
                    inp = ii
                    break
            py_ev = None
            if inp is not None:
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
                py_ev = res.eventualBG
            print(f" idx {real_idx}: ref {ref_ev} py {py_ev} err {err}")
        except Exception:
            print(f" idx_pos {enum_idx} err {err}")

    # Top 10 by absolute rate error
    rate_abs_sorted = sorted(
        enumerate(rate_errors),
        key=lambda x: abs(x[1]),
        reverse=True,
    )[:10]
    print("\nTop 10 rate errors (U/h):")
    for enum_idx, err in rate_abs_sorted:
        try:
            real_idx = compared_idxs[enum_idx]
            print(f" idx {real_idx}: rate_err {err}")
        except Exception:
            print(f" idx_pos {enum_idx} rate_err {err}")

    # Top 10 by absolute insulinReq error
    ins_abs_sorted = sorted(
        enumerate(ins_errors),
        key=lambda x: abs(x[1]),
        reverse=True,
    )[:10]
    print("\nTop 10 insulinReq errors (U):")
    for enum_idx, err in ins_abs_sorted:
        try:
            real_idx = compared_idxs[enum_idx]
            print(f" idx {real_idx}: ins_err {err}")
        except Exception:
            print(f" idx_pos {enum_idx} ins_err {err}")


if __name__ == "__main__":
    main()
