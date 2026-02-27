"""
Generate CSV with diffs between reference and python results and include input JSON.
Creates: tests/diffs_with_inputs.csv
Run:
  python -m aaps_emulator.tools.dump_diffs_and_inputs
"""

import csv
import json
import os

from aaps_emulator.analysis.compare_runner import run_compare_on_all_logs
from aaps_emulator.config import LOGS_PATH
from aaps_emulator.core.autoisf_algorithm import determine_basal_autoisf


def _rt_looks_like_autoisf(rt: dict) -> bool:
    """
    Heuristic: decide whether an RT dict contains a real AutoISF result
    (so its 'rate' / 'insulin_req' can be treated as a reference).
    Conservative: return True only when explicit markers are present.
    """
    if not isinstance(rt, dict):
        return False

    # explicit algorithm/source markers
    alg = rt.get("algorithm") or rt.get("algo") or rt.get("source")
    if alg and "auto" in str(alg).lower():
        return True

    # final_rate_source marker used in some logs
    frs = rt.get("final_rate_source") or rt.get("finalRateSource")
    if frs and "rt_rate" in str(frs).lower():
        return True

    # if rt explicitly contains a non-null insulin_req and a companion marker
    if "insulin_req" in rt and rt.get("insulin_req") is not None:
        # accept only if there is an explicit marker that this is an AutoISF result
        ins_src = rt.get("insulin_req_source") or rt.get("insulinReqSource")
        if ins_src and "auto" in str(ins_src).lower():
            return True

    # if rt contains a 'mode' or 'type' that explicitly mentions autoisf
    mode = rt.get("mode") or rt.get("type")
    return bool(mode and "auto" in str(mode).lower())


def main():
    out_csv = os.path.join("tests", "diffs_with_inputs.csv")
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
                "err_rate",
                "aaps_insreq_ref",
                "py_insreq",
                "err_ins",
                "autosens_ratio_ref",
                "autosens_ratio",
                "iob_ref",
                "iob_py",
                "smb_ref",
                "py_smb",
                "temp_basal_ref",
                "profile_basal",
                "bg",
                "delta",
                "profile_sens",
                "input_json",
            ]
        )

        for r, _b, inp in zip(rows, blocks, inputs, strict=True):
            idx = r.get("idx")

            # Extract objects
            gs = inp.get("glucose_status")
            autosens = inp.get("autosens")
            profile = inp.get("profile")
            rt = inp.get("rt")

            # Glucose
            bg = getattr(gs, "glucose", None)
            delta = getattr(gs, "delta", None)

            # Extract reference values from RT (conservative)
            eventual_ref = None
            rate_ref = None
            insulinReq_ref = None
            iob_ref = None

            if isinstance(rt, dict):
                # eventualBG is generally safe to extract for comparison
                eventual_ref = rt.get("eventual_bg") or rt.get("eventualBG") or rt.get("eventual")

                # iob numeric value (diagnostic)
                iob_ref = rt.get("iob")

                # Only treat rate/insulin_req as reference when RT clearly looks like an AutoISF result
                if _rt_looks_like_autoisf(rt):
                    rate_ref = rt.get("rate") if "rate" in rt else rt.get("deliveryRate")
                    insulinReq_ref = rt.get("insulin_req") if "insulin_req" in rt else rt.get("insulinReq")
                else:
                    # conservative: do not use RT rate/insulin_req as reference
                    rate_ref = None
                    insulinReq_ref = None

            # Python autosens
            autosens_ratio = getattr(autosens, "ratio", None)

            # Autosens reference does not exist in RT logs
            autosens_ratio_ref = None

            # SMB and temp basal do not exist in AutoISF RT logs (conservative)
            smb_ref = None
            temp_basal_ref = None

            # Python IOB
            iob_py = None
            if inp.get("iob_array"):
                first_iob = inp["iob_array"][0]
                iob_py = getattr(first_iob, "iob", None)

            # Profile
            profile_sens = getattr(profile, "sens", None)
            profile_basal = getattr(profile, "current_basal", None)

            # Run python algorithm
            errs = []
            logs = []
            res = determine_basal_autoisf(
                glucose_status=gs,
                currenttemp=inp.get("current_temp"),
                iob_data_array=inp.get("iob_array"),
                profile=profile,
                autosens_data=autosens,
                meal_data=inp.get("meal"),
                rt=rt,
                auto_isf_consoleError=errs,
                auto_isf_consoleLog=logs,
            )

            py_ev = res.eventualBG
            py_rate = res.rate
            py_ins = res.insulinReq
            py_smb = getattr(res, "smb", None)

            # Reference values
            ref_ev = eventual_ref
            ref_rate = rate_ref
            ref_ins = insulinReq_ref

            # Errors
            err_ev = None
            if py_ev is not None and ref_ev is not None:
                try:
                    err_ev = float(py_ev) - float(ref_ev)
                except Exception:
                    err_ev = None

            err_ins = None
            if py_ins is not None and ref_ins is not None:
                try:
                    err_ins = float(py_ins) - float(ref_ins)
                except Exception:
                    err_ins = None

            err_rate = None
            if py_rate is not None and ref_rate is not None:
                try:
                    err_rate = float(py_rate) - float(ref_rate)
                except Exception:
                    err_rate = None

            # Write row
            w.writerow(
                [
                    idx,
                    r.get("ts_s"),
                    ref_ev,
                    py_ev,
                    err_ev,
                    ref_rate,
                    py_rate,
                    err_rate,
                    ref_ins,
                    py_ins,
                    err_ins,
                    autosens_ratio_ref,
                    autosens_ratio,
                    iob_ref,
                    iob_py,
                    smb_ref,
                    py_smb,
                    temp_basal_ref,
                    profile_basal,
                    bg,
                    delta,
                    profile_sens,
                    json.dumps(inp, default=str),
                ]
            )

    print("Wrote", out_csv)


if __name__ == "__main__":
    main()
