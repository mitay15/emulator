# tools/debug_one_block.py
"""
Debug one or many mismatch_block_*.json files.

Usage:
    python -m aaps_emulator.tools.debug_one_block --file data/cache/mismatch_block_123.json
    python -m aaps_emulator.tools.debug_one_block --dir mismatches --out report.json

What it does:
- Loads mismatch JSON(s) produced by compare_runner (mismatch_block_*.json).
- Reconstructs inputs (uses `inputs` in the dump if present; otherwise tries to build from `block`).
- Runs the Python pipeline: run_predictions and run_autoisf_pipeline.
- Compares AAPS values (from dump) vs Python values field-by-field and array-by-array.
- Prints a step-by-step diff and a short list of heuristic suggestions where to look / what to change.
- Optionally writes a JSON report with diffs and suggestions.

Notes:
- This script is a diagnostic helper. It does not modify code.
- It uses project modules: runner.build_inputs, core.predictions, core.autoisf_pipeline, core.determine_basal, core.future_iob_engine.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aaps_emulator.core.autoisf_pipeline import run_autoisf_pipeline
from aaps_emulator.core.future_iob_engine import generate_future_iob
from aaps_emulator.core.predictions import run_predictions

# Import project modules (assumes script runs from project root)
from aaps_emulator.runner.build_inputs import build_inputs_from_block

# Tolerances
TOL_EVENTUAL_BG = 0.5  # mg/dL
TOL_VAR_SENS = 0.01
TOL_INSULIN = 0.1
TOL_RATE = 0.1


def safe_get(d: Dict[str, Any], *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d:
            return d[k]
    return default


def num(v) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def compare_scalar(
    name: str, aaps_val: Any, py_val: Any, tol: float
) -> Tuple[bool, float]:
    """
    Return (mismatch_bool, abs_diff)
    If either is None -> treat as no mismatch (caller can decide).
    """
    a = num(aaps_val)
    b = num(py_val)
    if a is None or b is None:
        return False, float("nan")
    diff = abs(a - b)
    return diff > tol, diff


def compare_arrays(
    aaps_arr: List[Any], py_arr: List[Any], tol: float
) -> Dict[str, Any]:
    """
    Compare two numeric arrays element-wise. Returns summary dict.
    """
    res = {
        "len_aaps": len(aaps_arr) if aaps_arr is not None else 0,
        "len_py": len(py_arr) if py_arr is not None else 0,
        "first_mismatch_index": None,
        "max_abs_diff": None,
        "mismatches": 0,
    }
    if not aaps_arr or not py_arr:
        return res
    max_diff = 0.0
    mismatches = 0
    first_idx = None
    L = min(len(aaps_arr), len(py_arr))
    for i in range(L):
        try:
            ai = float(aaps_arr[i])
            bi = float(py_arr[i])
            d = abs(ai - bi)
            if d > tol:
                mismatches += 1
                if first_idx is None:
                    first_idx = i
            if d > max_diff:
                max_diff = d
        except Exception:
            # non-numeric -> count as mismatch
            mismatches += 1
            if first_idx is None:
                first_idx = i
    res["first_mismatch_index"] = first_idx
    res["max_abs_diff"] = max_diff
    res["mismatches"] = mismatches
    return res


def load_mismatch(path: Path) -> Dict[str, Any]:
    txt = path.read_text(encoding="utf-8")
    return json.loads(txt)


def reconstruct_inputs_from_dump(
    dump: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Any]:
    """
    Prefer dump['inputs'] if present (already serialized). Otherwise use dump['block'].
    Returns (block_objs, inputs_hint)
    """
    inputs = dump.get("inputs")
    if inputs:
        # If inputs is a dict with glucose_status/profile etc, we can try to build AutoIsfInputs
        # But compare_runner already serializes inputs.* as dataclasses; build_inputs_from_block expects block list.
        # We'll try to reconstruct a minimal block: GlucoseStatusAutoIsf + profile + IobTotal entries
        block_objs = []
        gs = inputs.get("glucose_status")
        if gs:
            block_objs.append(gs)
        if inputs.get("current_temp"):
            block_objs.append(inputs.get("current_temp"))
        # iob_data_array may be list of dicts
        for iob in inputs.get("iob_data_array", []):
            block_objs.append(iob)
        if inputs.get("profile"):
            block_objs.append(inputs.get("profile"))
        if inputs.get("autosens"):
            block_objs.append(inputs.get("autosens"))
        if inputs.get("meal"):
            block_objs.append(inputs.get("meal"))
        return block_objs, inputs
    # fallback: try 'block' field (raw block)
    block = dump.get("block") or dump.get("raw_block") or dump.get("aaps_rt") or []
    # block may be serialized already; ensure it's a list
    if isinstance(block, dict):
        # sometimes block is a dict of objects; try to extract values
        # if it looks like RT, wrap it
        return [block], None
    return block, None


def run_and_trace(block_objs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build inputs via build_inputs_from_block and run predictions + pipeline.
    Returns a dict with 'inputs', 'pred', 'pipeline' (variable_sens, pred, dosing) and some generated traces.
    """
    inputs = build_inputs_from_block(block_objs)
    # --- debug prints: show what pipeline actually receives ---
    print(
        "DEBUG: inputs.profile.variable_sens =",
        getattr(inputs.profile, "variable_sens", None),
    )
    print(
        "DEBUG: inputs.profile._variable_sens_from_rt =",
        getattr(inputs.profile, "_variable_sens_from_rt", None),
    )
    print("DEBUG: inputs.autosens.ratio =", getattr(inputs.autosens, "ratio", None))
    # ---------------------------------------------------------

    # run predictions
    pred = run_predictions(inputs)
    # run pipeline (variable_sens, pred2, dosing)
    variable_sens, pred2, dosing = run_autoisf_pipeline(inputs)
    # also compute future_iob for first iob entry if present
    future_iob = []
    if inputs.iob_data_array:
        try:
            future_iob = generate_future_iob(inputs.iob_data_array[0])
        except Exception:
            future_iob = []
    return {
        "inputs": inputs,
        "pred": pred,
        "pipeline": {
            "variable_sens": variable_sens,
            "pred": pred2,
            "dosing": dosing,
        },
        "future_iob": future_iob,
    }


def heuristic_suggestions(dump: Dict[str, Any], trace: Dict[str, Any]) -> List[str]:
    """
    Based on differences, produce heuristic suggestions where to look and what to change.
    These are *suggestions* (not definitive fixes).
    """
    suggestions: List[str] = []
    aaps_rt = dump.get("aaps_rt") or dump.get("aaps", {}) or {}
    # Extract AAPS values
    aaps_eventual = safe_get(aaps_rt, "eventualBG", "eventual_bg", default=None)
    aaps_var_sens = safe_get(aaps_rt, "variable_sens", default=None)
    safe_get(aaps_rt, "minPredBG", "min_pred_bg", default=None)
    safe_get(aaps_rt, "minGuardBG", "min_guard_bg", default=None)
    aaps_insulinReq = safe_get(aaps_rt, "insulinReq", "insulin_req", default=None)
    aaps_rate = safe_get(aaps_rt, "rate", default=None)

    py_vs = trace["pipeline"]["variable_sens"]
    py_pred = trace["pipeline"]["pred"]
    py_dosing = trace["pipeline"]["dosing"]

    # Compare variable sens
    if aaps_var_sens is not None and py_vs is not None:
        if abs(num(aaps_var_sens) - num(py_vs)) > TOL_VAR_SENS:
            suggestions.append(
                "variable_sens differs: check autoisf_module.compute_variable_sens and weight application "
                "(bgAccel_ISF_weight, bgBrake_ISF_weight, pp_ISF_weight, dura_ISF_weight)."
            )

    # Compare eventualBG
    if aaps_eventual is not None and getattr(py_pred, "eventual_bg", None) is not None:
        if (
            abs(num(aaps_eventual) - num(getattr(py_pred, "eventual_bg", None)))
            > TOL_EVENTUAL_BG
        ):
            suggestions.append(
                "eventualBG differs: check predictions.run_predictions internals: "
                "sens selection, IOB activity curve (future_iob_engine), carb absorption (CI), and rounding."
            )

    # Compare pred_iob arrays
    aaps_pred_iob = safe_get(aaps_rt, "pred_iob", "predIob", default=None) or safe_get(
        dump, "pred", {}
    ).get("pred_iob")
    py_pred_iob = getattr(py_pred, "pred_iob", None)
    if aaps_pred_iob and py_pred_iob:
        arr_cmp = compare_arrays(aaps_pred_iob, py_pred_iob, tol=0.5)
        if arr_cmp["mismatches"] > 0:
            suggestions.append(
                "pred_iob arrays mismatch: likely cause is different IOB activity curve. "
                "Compare future_iob_engine._oref0_activity_fraction with AAPS DIA curve."
            )

    # Compare pred_cob arrays
    aaps_pred_cob = safe_get(aaps_rt, "pred_cob", "predCob", default=None) or safe_get(
        dump, "pred", {}
    ).get("pred_cob")
    py_pred_cob = getattr(py_pred, "pred_cob", None)
    if aaps_pred_cob and py_pred_cob:
        arr_cmp = compare_arrays(aaps_pred_cob, py_pred_cob, tol=1.0)
        if arr_cmp["mismatches"] > 0:
            suggestions.append(
                "pred_cob arrays mismatch: check carb absorption model (predictions.py), CI/CID calculations and carb ratio handling."
            )

    # Compare dosing differences
    if aaps_insulinReq is not None and py_dosing is not None:
        if (
            abs(num(aaps_insulinReq) - num(getattr(py_dosing, "insulinReq", None)))
            > TOL_INSULIN
        ):
            suggestions.append(
                "insulinReq differs: check determine_basal logic (minPredBG/minGuardBG handling, clamps, max_iob, safety multipliers)."
            )
    if aaps_rate is not None and py_dosing is not None:
        if abs(num(aaps_rate) - num(getattr(py_dosing, "rate", None))) > TOL_RATE:
            suggestions.append(
                "basal rate differs: check determine_basal rate calculation and rounding/limits (max_basal, current_basal_safety_multiplier)."
            )

    # Rounding heuristic
    # If many small differences (~0.01-0.5) across arrays, suggest rounding differences
    def many_small_diffs(a, b):
        if not a or not b:
            return False
        cnt_small = 0
        L = min(len(a), len(b))
        for i in range(L):
            try:
                d = abs(float(a[i]) - float(b[i]))
                if 0.001 < d < 0.6:
                    cnt_small += 1
            except Exception:
                continue
        return cnt_small > max(3, L // 4)

    if aaps_pred_iob and py_pred_iob and many_small_diffs(aaps_pred_iob, py_pred_iob):
        suggestions.append(
            "Many small differences detected across prediction arrays: check numeric rounding strategy (round half even vs round half away from zero). "
            "Look at utils.round_half_even usage and places where values are rounded before being stored."
        )

    # If no suggestions, add generic guidance
    if not suggestions:
        suggestions.append(
            "No strong heuristic found. Inspect intermediate traces: sens, IOB activity, CI/CID, and determine_basal clamps."
        )

    # Add file pointers for likely files to inspect
    file_hints = [
        ("predictions", "aaps_emulator/core/predictions.py"),
        ("future_iob_engine", "aaps_emulator/core/future_iob_engine.py"),
        ("autoisf_module", "aaps_emulator/core/autoisf_module.py"),
        ("determine_basal", "aaps_emulator/core/determine_basal.py"),
        ("utils", "aaps_emulator/core/utils.py"),
    ]
    suggestions.append(
        "Files to inspect: " + ", ".join(f"{n} ({p})" for n, p in file_hints)
    )
    return suggestions


def pretty_print_diff(dump: Dict[str, Any], trace: Dict[str, Any]) -> Dict[str, Any]:
    """
    Print a human-friendly diff and return a structured report dict.
    """
    report: Dict[str, Any] = {}
    aaps_rt = dump.get("aaps_rt") or dump.get("aaps", {}) or {}
    dump.get("row", {}) or {}

    py_vs = trace["pipeline"]["variable_sens"]
    py_pred = trace["pipeline"]["pred"]
    py_dosing = trace["pipeline"]["dosing"]

    print("\n" + "=" * 80)
    print("MISMATCH DIAGNOSTIC")
    print("=" * 80)

    # Variable sens
    aaps_vs = safe_get(aaps_rt, "variable_sens", "variableSens", default=None)
    mismatch_vs, diff_vs = compare_scalar("variable_sens", aaps_vs, py_vs, TOL_VAR_SENS)
    print(f"\nvariable_sens: AAPS={aaps_vs}  PY={py_vs}  diff={diff_vs}")
    report["variable_sens"] = {
        "aaps": aaps_vs,
        "py": py_vs,
        "diff": diff_vs,
        "mismatch": mismatch_vs,
    }

    # eventualBG
    aaps_eventual = safe_get(aaps_rt, "eventualBG", "eventual_bg", default=None)
    py_eventual = getattr(py_pred, "eventual_bg", None)
    mismatch_ev, diff_ev = compare_scalar(
        "eventualBG", aaps_eventual, py_eventual, TOL_EVENTUAL_BG
    )
    print(f"eventualBG: AAPS={aaps_eventual}  PY={py_eventual}  diff={diff_ev}")
    report["eventualBG"] = {
        "aaps": aaps_eventual,
        "py": py_eventual,
        "diff": diff_ev,
        "mismatch": mismatch_ev,
    }

    # minPredBG / minGuardBG
    aaps_min_pred = safe_get(aaps_rt, "minPredBG", "min_pred_bg", default=None)
    py_min_pred = getattr(py_pred, "min_pred_bg", None)
    mismatch_mp, diff_mp = compare_scalar(
        "minPredBG", aaps_min_pred, py_min_pred, TOL_EVENTUAL_BG
    )
    print(f"minPredBG: AAPS={aaps_min_pred}  PY={py_min_pred}  diff={diff_mp}")
    report["minPredBG"] = {
        "aaps": aaps_min_pred,
        "py": py_min_pred,
        "diff": diff_mp,
        "mismatch": mismatch_mp,
    }

    aaps_min_guard = safe_get(aaps_rt, "minGuardBG", "min_guard_bg", default=None)
    py_min_guard = getattr(py_pred, "min_guard_bg", None)
    mismatch_mg, diff_mg = compare_scalar(
        "minGuardBG", aaps_min_guard, py_min_guard, TOL_EVENTUAL_BG
    )
    print(f"minGuardBG: AAPS={aaps_min_guard}  PY={py_min_guard}  diff={diff_mg}")
    report["minGuardBG"] = {
        "aaps": aaps_min_guard,
        "py": py_min_guard,
        "diff": diff_mg,
        "mismatch": mismatch_mg,
    }

    # pred arrays
    def print_arr_cmp(name, aaps_arr, py_arr, tol):
        cmp = compare_arrays(aaps_arr or [], py_arr or [], tol)
        print(
            f"\n{name}: len AAPS={cmp['len_aaps']} len PY={cmp['len_py']} mismatches={cmp['mismatches']} max_diff={cmp['max_abs_diff']} first_mismatch_index={cmp['first_mismatch_index']}"
        )
        return cmp

    aaps_pred_iob = safe_get(aaps_rt, "pred_iob", "predIob", default=None) or safe_get(
        dump, "pred", {}
    ).get("pred_iob")
    py_pred_iob = getattr(py_pred, "pred_iob", None)
    report["pred_iob_cmp"] = print_arr_cmp(
        "pred_iob", aaps_pred_iob, py_pred_iob, tol=0.5
    )

    aaps_pred_cob = safe_get(aaps_rt, "pred_cob", "predCob", default=None) or safe_get(
        dump, "pred", {}
    ).get("pred_cob")
    py_pred_cob = getattr(py_pred, "pred_cob", None)
    report["pred_cob_cmp"] = print_arr_cmp(
        "pred_cob", aaps_pred_cob, py_pred_cob, tol=1.0
    )

    aaps_pred_uam = safe_get(aaps_rt, "pred_uam", "predUam", default=None) or safe_get(
        dump, "pred", {}
    ).get("pred_uam")
    py_pred_uam = getattr(py_pred, "pred_uam", None)
    report["pred_uam_cmp"] = print_arr_cmp(
        "pred_uam", aaps_pred_uam, py_pred_uam, tol=1.0
    )

    aaps_pred_zt = safe_get(aaps_rt, "pred_zt", "predZt", default=None) or safe_get(
        dump, "pred", {}
    ).get("pred_zt")
    py_pred_zt = getattr(py_pred, "pred_zt", None)
    report["pred_zt_cmp"] = print_arr_cmp("pred_zt", aaps_pred_zt, py_pred_zt, tol=1.0)

    # dosing
    aaps_insulinReq = safe_get(aaps_rt, "insulinReq", "insulin_req", default=None)
    py_insulinReq = getattr(py_dosing, "insulinReq", None)
    mismatch_ir, diff_ir = compare_scalar(
        "insulinReq", aaps_insulinReq, py_insulinReq, TOL_INSULIN
    )
    print(f"\ninsulinReq: AAPS={aaps_insulinReq}  PY={py_insulinReq}  diff={diff_ir}")
    report["insulinReq"] = {
        "aaps": aaps_insulinReq,
        "py": py_insulinReq,
        "diff": diff_ir,
        "mismatch": mismatch_ir,
    }

    aaps_rate = safe_get(aaps_rt, "rate", default=None)
    py_rate = getattr(py_dosing, "rate", None)
    mismatch_rate, diff_rate = compare_scalar("rate", aaps_rate, py_rate, TOL_RATE)
    print(f"rate: AAPS={aaps_rate}  PY={py_rate}  diff={diff_rate}")
    report["rate"] = {
        "aaps": aaps_rate,
        "py": py_rate,
        "diff": diff_rate,
        "mismatch": mismatch_rate,
    }

    aaps_duration = safe_get(aaps_rt, "duration", default=None)
    py_duration = getattr(py_dosing, "duration", None)
    mismatch_dur, diff_dur = compare_scalar(
        "duration", aaps_duration, py_duration, tol=1.0
    )
    print(f"duration: AAPS={aaps_duration}  PY={py_duration}  diff={diff_dur}")
    report["duration"] = {
        "aaps": aaps_duration,
        "py": py_duration,
        "diff": diff_dur,
        "mismatch": mismatch_dur,
    }

    # suggestions
    suggestions = heuristic_suggestions(dump, trace)
    print("\n\nSUGGESTIONS / HINTS")
    print("-------------------")
    for s in suggestions:
        print("- " + s)
    report["suggestions"] = suggestions

    return report


def process_file(path: Path) -> Dict[str, Any]:
    print(f"\nProcessing {path}")
    dump = load_mismatch(path)
    # --- inject RT into block if missing ---
    try:
        if "aaps_rt" in dump:
            rt = dump["aaps_rt"]
            if isinstance(rt, dict):
                block = dump.get("block") or dump.get("raw_block") or []
                if isinstance(block, dict):
                    block = [block]
                # если в block нет RT — добавляем
                if not any(
                    isinstance(o, dict) and o.get("__type__") == "RT" for o in block
                ):
                    block.append(rt)
                    print("DEBUG: Injected RT into block")
                dump["block"] = block
    except Exception as e:
        print("DEBUG: RT injection failed:", e)
    # ----------------------------------------

    # безопасно инициализируем block_objs
    block_objs = []
    inputs_hint = None

    # Попытка реконструировать входы; если не получилось — сохраняем дамп и возвращаем ошибку
    try:
        block_objs, inputs_hint = reconstruct_inputs_from_dump(dump)
        # --- inject RT directly into block_objs ---
        try:
            rt = dump.get("aaps_rt")
            if isinstance(rt, dict):
                if not any(
                    isinstance(o, dict) and o.get("__type__") == "RT"
                    for o in block_objs
                ):
                    block_objs.append(rt)
                    print("DEBUG: Injected RT into block_objs")
        except Exception as e:
            print("DEBUG: RT injection into block_objs failed:", e)
        # ------------------------------------------

        if not block_objs:
            block_objs = dump.get("block") or dump.get("raw_block") or []
            if isinstance(block_objs, dict):
                block_objs = [block_objs]
    except Exception as e:
        err_path = Path("aaps_emulator/data/cache/parsed_block_on_error.json")
        err_path.parent.mkdir(parents=True, exist_ok=True)
        err_path.write_text(
            json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Error while building inputs, dump saved to {err_path}")
        return {
            "file": str(path),
            "error": f"Error reconstructing inputs: {e}",
            "saved_dump": str(err_path),
        }

    if not block_objs:
        return {
            "file": str(path),
            "error": "No block objects could be reconstructed from dump",
            "saved_dump": None,
        }

    try:
        # DEBUG: показать, что лежит в дампе и какие inputs пришли из reconstruct
        print("DEBUG_DUMP: aaps_rt =", dump.get("aaps_rt"))
        print("DEBUG_DUMP: inputs (keys) =", list((dump.get("inputs") or {}).keys()))

        trace = run_and_trace(block_objs)
        report = pretty_print_diff(dump, trace)
        report_meta = {
            "file": str(path),
            "aaps_rt": dump.get("aaps_rt"),
            "row": dump.get("row"),
            "report": report,
        }
        return report_meta
    except Exception as e:
        err_inputs_path = Path("data/cache/failed_inputs_for_pipeline.json")
        err_inputs_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            err_inputs_path.write_text(
                json.dumps(block_objs, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            err_inputs_path.write_text(str(block_objs), encoding="utf-8")
        print(f"Error while running pipeline, inputs saved to {err_inputs_path}")
        return {
            "file": str(path),
            "error": f"Error running pipeline: {e}",
            "saved_inputs": str(err_inputs_path),
        }


def main():
    parser = argparse.ArgumentParser(description="Debug mismatch_block_*.json files")
    parser.add_argument("--file", type=str, help="Path to single mismatch JSON file")
    parser.add_argument("--dir", type=str, help="Directory with mismatch JSON files")
    parser.add_argument("--out", type=str, help="Optional output JSON report path")
    args = parser.parse_args()

    files: List[Path] = []
    if args.file:
        p = Path(args.file)
        if not p.exists():
            print("File not found:", p)
            return
        files.append(p)
    elif args.dir:
        d = Path(args.dir)
        if not d.exists():
            print("Directory not found:", d)
            return
        files = sorted([p for p in d.glob("mismatch_block_*.json")])
    else:
        # default: look in mismatches/ and data/cache
        files = sorted(
            list(Path("mismatches").glob("mismatch_block_*.json"))
            + list(Path("data/cache").glob("mismatch_block_*.json"))
        )

    if not files:
        print("No mismatch files found.")
        return

    all_reports = []
    for f in files:
        try:
            rep = process_file(f)
            all_reports.append(rep)
        except Exception as e:
            print(f"Error processing {f}: {e}")

    if args.out:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(
            json.dumps(all_reports, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nWrote report to {outp}")

    print("\nDone.")


if __name__ == "__main__":
    main()
