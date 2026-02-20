# aaps_emulator/tools/dump_diffs_and_inputs.py
"""
Generate CSV with diffs between reference and python results and include input JSON.
Creates: aaps_emulator/tests/diffs_with_inputs.csv
Run from inside aaps_emulator:
  python -m tools.dump_diffs_and_inputs
"""
import csv
import os
import json
from analysis.compare_runner import run_compare_on_all_logs
from core.autoisf_algorithm import determine_basal_autoisf

def main():
    out_csv = os.path.join("aaps_emulator", "tests", "diffs_with_inputs.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)

    rows, blocks, inputs = run_compare_on_all_logs("logs")

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["idx","ts_s","aaps_eventual_ref","py_eventual","err_ev","aaps_rate_ref","py_rate","aaps_insreq_ref","py_insreq","input_json"])
        for r, b, inp in zip(rows, blocks, inputs):
            idx = r.get("idx")
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
                auto_isf_consoleLog=logs
            )
            py_ev = res.eventualBG if res.eventualBG is not None else None
            py_rate = res.rate if res.rate is not None else 0.0
            py_ins = res.insulinReq if res.insulinReq is not None else None
            ref_ev = r.get("aaps_eventual", None)
            ref_rate = r.get("aaps_rate", None)
            ref_ins = r.get("aaps_insreq", None)
            err_ev = None
            try:
                if py_ev is not None and ref_ev is not None:
                    err_ev = float(py_ev) - float(ref_ev)
            except Exception:
                err_ev = None

            w.writerow([
                idx,
                r.get("ts_s"),
                ref_ev,
                py_ev,
                err_ev,
                ref_rate,
                py_rate,
                ref_ins,
                py_ins,
                json.dumps(inp, default=str)
            ])

    print("Wrote", out_csv)

if __name__ == "__main__":
    main()
