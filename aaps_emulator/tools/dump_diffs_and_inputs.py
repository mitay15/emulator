"""
Generate CSV with diffs between reference and python results and include input JSON.
Creates: aaps_emulator/tests/diffs_with_inputs.csv
Run:
  python -m aaps_emulator.tools.dump_diffs_and_inputs
"""

import csv
import json
import os

from aaps_emulator.analysis.compare_runner import run_compare_on_all_logs
from aaps_emulator.config import LOGS_PATH
from aaps_emulator.core.autoisf_algorithm import determine_basal_autoisf


def main():
    out_csv = os.path.join("aaps_emulator", "tests", "diffs_with_inputs.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)

    rows, blocks, inputs = run_compare_on_all_logs(str(LOGS_PATH))

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "idx",
                "ts_s",
                "aaps_eventual_ref",
                "py_eventual",
                "err_ev",
                "aaps_rate_ref",
                "py_rate",
                "aaps_insreq_ref",
                "py_insreq",
                "bg",
                "delta",
                "autosens_ratio",
                "profile_sens",
                "profile_basal",
                "input_json",
            ]
        )
        for r, _b, inp in zip(rows, blocks, inputs, strict=True):
            idx = r.get("idx")

            gs = inp.get("glucose_status")
            autosens = inp.get("autosens")
            profile = inp.get("profile")

            bg = getattr(gs, "glucose", None)
            delta = getattr(gs, "delta", None)
            autosens_ratio = getattr(autosens, "ratio", None)
            profile_sens = getattr(profile, "sens", None)
            profile_basal = getattr(profile, "current_basal", None)

            errs = []
            logs = []
            res = determine_basal_autoisf(
                glucose_status=gs,
                currenttemp=inp.get("current_temp"),
                iob_data_array=inp.get("iob_array"),
                profile=profile,
                autosens_data=autosens,
                meal_data=inp.get("meal"),
                rt=inp.get("rt"),
                auto_isf_consoleError=errs,
                auto_isf_consoleLog=logs,
            )
            py_ev = res.eventualBG
            py_rate = res.rate
            py_ins = res.insulinReq

            ref_ev = r.get("aaps_eventual")
            ref_rate = r.get("aaps_rate")
            ref_ins = r.get("aaps_insreq")

            err_ev = None
            if py_ev is not None and ref_ev is not None:
                try:
                    err_ev = float(py_ev) - float(ref_ev)
                except Exception:
                    err_ev = None

            w.writerow(
                [
                    idx,
                    r.get("ts_s"),
                    ref_ev,
                    py_ev,
                    err_ev,
                    ref_rate,
                    py_rate,
                    ref_ins,
                    py_ins,
                    bg,
                    delta,
                    autosens_ratio,
                    profile_sens,
                    profile_basal,
                    json.dumps(inp, default=str),
                ]
            )

    print("Wrote", out_csv)


if __name__ == "__main__":
    main()
