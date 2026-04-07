# aaps_emulator/core/block_utils.py

from __future__ import annotations
from typing import Any, Dict, Optional
from pathlib import Path

from aaps_emulator.runner.load_logs import load_logs


# ============================================================
# LOAD & GROUP BLOCKS
# ============================================================
def load_and_group_blocks(logs_dir: Path):
    """
    Быстрая и чистая версия:
    - читает все логи
    - сортирует по timestamp/date
    - группирует блоки по GS → ... → RT
    """
    paths = sorted(
        list(logs_dir.rglob("*.json"))
        + list(logs_dir.rglob("*.zip"))
        + list(logs_dir.rglob("*.log")),
        key=lambda p: p.name
    )

    all_objs = []
    for p in paths:
        parsed = load_logs(p)
        for obj in parsed:
            if isinstance(obj, dict):
                obj["_log_path"] = str(p)
        all_objs.extend(parsed)

    # сортируем по timestamp/date
    def ts(o):
        if isinstance(o, dict):
            return o.get("timestamp") or o.get("date") or 0
        return 0

    all_objs.sort(key=ts)

    blocks = []
    current = []

    for obj in all_objs:
        if isinstance(obj, dict) and obj.get("__type__") == "GlucoseStatusAutoIsf":
            # начинаем новый блок
            if current:
                blocks.append(current)
            current = [obj]
        else:
            if current:
                current.append(obj)
                if isinstance(obj, dict) and obj.get("__type__") == "RT":
                    blocks.append(current)
                    current = []

    if current:
        blocks.append(current)

    # финальная упаковка
    result = []
    for idx, block in enumerate(blocks, start=1):
        gs = block[0]
        ts = gs.get("date") or gs.get("timestamp") or 0
        result.append((idx, ts, block))

    return result


# ============================================================
# RESTORE INPUTS (meal + profile)
# ============================================================
def restore_inputs(inputs, inputs_before: Optional[Dict[str, Any]]):
    if not inputs_before:
        return inputs

    inner = inputs_before.get("inputs") or {}

    # meal
    m = inner.get("meal")
    if m:
        try:
            inputs.meal.carbs = float(m.get("carbs", 0.0) or 0.0)
            inputs.meal.mealCOB = float(m.get("mealCOB", 0.0) or 0.0)
            inputs.meal.slopeFromMaxDeviation = float(m.get("slopeFromMaxDeviation", 0.0) or 0.0)
            inputs.meal.slopeFromMinDeviation = float(m.get("slopeFromMinDeviation", 0.0) or 0.0)
            inputs.meal.lastBolusTime = m.get("lastBolusTime")
            inputs.meal.lastCarbTime = m.get("lastCarbTime")
        except Exception:
            pass

    # profile
    prof_dict = inner.get("profile")
    if prof_dict:
        prof_obj = getattr(inputs, "profile", None)
        if prof_obj:
            for k, v in prof_dict.items():
                try:
                    setattr(prof_obj, k, v)
                except Exception:
                    pass

    return inputs


# ============================================================
# EXTRACT PRED ARRAY
# ============================================================
def extract_pred_array(pred):
    if pred is None:
        return []

    predBGs = None

    if hasattr(pred, "predBGs"):
        predBGs = getattr(pred, "predBGs", None)

    if predBGs is None and isinstance(pred, dict):
        predBGs = pred.get("predBGs")

    if isinstance(predBGs, dict):
        arr = (
            predBGs.get("UAM")
            or predBGs.get("IOB")
            or predBGs.get("ZT")
            or []
        )
    elif isinstance(pred, list):
        arr = pred
    else:
        arr = []

    out = []
    for v in arr:
        try:
            out.append(float(v))
        except Exception:
            out.append(None)
    return out
