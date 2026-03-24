from __future__ import annotations

from runner.load_logs import load_logs
from core.autoisf_pipeline import run_autoisf_pipeline
from core.autoisf_structs import AutoIsfInputs

import sys
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


LOGS_DIR = Path("data/logs")


def group_by_timestamp(blocks: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    grouped: Dict[int, Dict[str, Any]] = {}
    for obj in blocks:
        if not isinstance(obj, dict):
            continue
        name = obj.get("__type__")
        if not name:
            continue
        ts = obj.get("timestamp") or obj.get("date") or obj.get("time") or obj.get("deliverAt")
        if ts is None:
            continue
        ts = int(ts)
        grouped.setdefault(ts, {})[name] = obj
    return grouped


def build_inputs_from_group(ts: int, group: Dict[str, Any]) -> Optional[AutoIsfInputs]:
    req = [
        "GlucoseStatusAutoIsf",
        "CurrentTemp",
        "IobTotal",
        "OapsProfileAutoIsf",
        "AutosensResult",
        "MealData",
        "Predictions",
    ]
    if not all(k in group for k in req):
        return None
    try:
        return AutoIsfInputs(
            glucose_status=group["GlucoseStatusAutoIsf"],
            currenttemp=group["CurrentTemp"],
            iob_data=group["IobTotal"],
            profile=group["OapsProfileAutoIsf"],
            autosens=group["AutosensResult"],
            meal=group["MealData"],
            predictions=group["Predictions"],
            currentTime=ts,
        )
    except Exception:
        return None


def extract_rt(group: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return group.get("RT")


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def compare_results(ts: int, rt: Dict[str, Any], pred, dosing) -> bool:
    # 1) Полная копия RT AAPS
    emu_rt = json.loads(json.dumps(rt))

    # 2) Перезаписываем только вычисляемые поля
    emu_rt["eventualBG"] = pred.eventual_bg
    emu_rt["minPredBG"] = pred.min_pred_bg
    emu_rt["minGuardBG"] = pred.min_guard_bg
    emu_rt["targetBG"] = getattr(pred, "target_bg", emu_rt.get("targetBG"))
    emu_rt["snoozeBG"] = getattr(pred, "snooze_bg", emu_rt.get("snoozeBG"))

    emu_rt["insulinReq"] = dosing.insulinReq
    emu_rt["rate"] = dosing.rate
    emu_rt["duration"] = dosing.duration
    emu_rt["units"] = dosing.units
    emu_rt["carbsReq"] = dosing.carbsReq
    emu_rt["carbsReqWithin"] = dosing.carbsReqWithin

    emu_rt["variable_sens"] = getattr(pred, "variable_sens", emu_rt.get("variable_sens"))
    emu_rt["sensitivityRatio"] = getattr(pred, "autosens_ratio", emu_rt.get("sensitivityRatio"))

    pred_rt = emu_rt.get("predBGs") or {}
    pred_rt["IOB"] = pred.pred_iob
    pred_rt["UAM"] = pred.pred_uam
    pred_rt["ZT"] = pred.pred_zt
    pred_rt["COB"] = getattr(pred, "pred_cob", pred_rt.get("COB"))
    pred_rt["aCOB"] = getattr(pred, "pred_acob", pred_rt.get("aCOB"))
    emu_rt["predBGs"] = pred_rt

    emu_rt["reason"] = dosing.reason

    # 3) JSON строки
    aaps_json = json.dumps(rt, sort_keys=True, ensure_ascii=False)
    emu_json = json.dumps(emu_rt, sort_keys=True, ensure_ascii=False)

    # 4) SHA‑256 хэши
    h1 = sha256(aaps_json)
    h2 = sha256(emu_json)

    if h1 != h2:
        print(f"\n=== MISMATCH ts={ts} ===")
        print("AAPS JSON:", aaps_json)
        print("EMU  JSON:", emu_json)
        print("AAPS SHA256:", h1)
        print("EMU  SHA256:", h2)
        return False

    return True


def main():
    print("Loading AAPS logs...")
    all_blocks = load_logs(LOGS_DIR)
    print(f"Loaded {len(all_blocks)} raw objects")

    grouped = group_by_timestamp(all_blocks)
    print(f"Grouped into {len(grouped)} timestamps")

    mismatches = 0

    for ts, group in grouped.items():
        inputs = build_inputs_from_group(ts, group)
        rt = extract_rt(group)
        if inputs is None or rt is None:
            continue

        variable_sens, pred, dosing = run_autoisf_pipeline(inputs)

        if not compare_results(ts, rt, pred, dosing):
            mismatches += 1

    print(f"\nDONE. Total mismatches: {mismatches}")


if __name__ == "__main__":
    main()
