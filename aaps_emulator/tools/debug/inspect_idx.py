"""
Compact inspector for a single idx.
Usage:
  python -m aaps_emulator.tools.debug.inspect_idx --idx 11
"""

import argparse
from pprint import pprint

from aaps_emulator.analysis.compare_runner import run_compare_on_all_logs
from aaps_emulator.core.autoisf_algorithm import determine_basal_autoisf


def compact(obj):
    """Return a compact dict for dataclasses/objects."""
    if obj is None:
        return None
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return obj


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--idx", type=int, required=True)
    p.add_argument("--logs", default="aaps_emulator/logs")
    args = p.parse_args()

    rows, blocks, inputs = run_compare_on_all_logs(args.logs)

    for r, _b, inp in zip(rows, blocks, inputs, strict=True):
        if r["idx"] != args.idx:
            continue

        print("\n==================== IDX", args.idx, "====================")

        # --- BASIC ROW INFO ---
        print("\n--- ROW ---")
        print({k: r[k] for k in ["idx", "ts_s"] if k in r})

        # --- RT SNIPPET ---
        print("\n--- RT ---")
        rt = inp.get("rt")
        if isinstance(rt, dict):
            keys = ["bg", "eventual_bg", "rate", "insulin_req", "iob", "cob", "duration"]
            print({k: rt.get(k) for k in keys})
        else:
            print("RT missing")

        # --- INPUTS (compact) ---
        print("\n--- INPUTS ---")
        print("glucose_status:", compact(inp.get("glucose_status")))
        print("autosens:", compact(inp.get("autosens")))
        print("profile:", compact(inp.get("profile")))
        print("current_temp:", compact(inp.get("current_temp")))
        print("meal:", compact(inp.get("meal")))
        print("iob_array:", [compact(x) for x in (inp.get("iob_array") or [])])

        # --- PYTHON AutoISF ---
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

        print("\n--- PYTHON RESULT ---")
        print(
            {
                "eventualBG": res.eventualBG,
                "rate": res.rate,
                "insulinReq": res.insulinReq,
                "smb": getattr(res, "smb", None),
            }
        )

        # --- AAPS reference ---
        print("\n--- AAPS REFERENCE ---")
        print(
            {
                "eventualBG_ref": r.get("aaps_eventual_ref"),
                "rate_ref": r.get("aaps_rate_ref"),
                "insulinReq_ref": r.get("aaps_insreq_ref"),
            }
        )

        # --- ERRORS ---
        print("\n--- ERRORS ---")
        print(
            {
                "err_ev": r.get("err_ev"),
                "err_rate": r.get("err_rate"),
                "err_ins": r.get("err_ins"),
            }
        )

        # --- LOGS ---
        print("\n--- AUTOISF LOGS (first 20 lines) ---")
        for line in logs[:20]:
            print(line)

        print("\n--- AUTOISF ERRORS ---")
        pprint(errs)

        print("\n====================================================\n")
        return

    print("idx not found:", args.idx)


if __name__ == "__main__":
    main()
