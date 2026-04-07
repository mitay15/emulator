# aaps_emulator/core/aps_what_if.py

from __future__ import annotations
from typing import Any, Dict, List, Tuple
from datetime import datetime, timedelta
import copy
import hashlib
import json

from aaps_emulator.core.block_utils import extract_pred_array, restore_inputs
from aaps_emulator.runner.build_inputs import build_inputs_from_block
from aaps_emulator.core.autoisf_pipeline import run_autoisf_pipeline
from aaps_emulator.core.cache import AUTOISF_CACHE, AUTOISF_SIM_CACHE


def _make_sim_cache_key(inputs, profile_override: Dict[str, Any]) -> Tuple[int, str] | None:
    """
    Формирует ключ кэша для симуляции:
    (timestamp, hash(profile_override))
    """
    gs = getattr(inputs, "glucose_status", None)
    ts = getattr(gs, "date", None)
    if ts is None:
        return None

    try:
        override_key = hashlib.md5(
            json.dumps(profile_override, sort_keys=True).encode("utf-8")
        ).hexdigest()
    except Exception:
        return None

    return ts, override_key


def _run_single(inputs, profile_override: Dict[str, Any]):
    """
    Запуск симуляции для одного блока.
    Возвращает (var, pred, dosing).
    Если profile_override пустой — просто прогоняет оригинальный pipeline.
    Если не пустой — применяет override и использует кэш симуляций.
    """
    # без override → просто оригинальный прогон
    if not profile_override:
        return run_autoisf_pipeline(inputs)

    # есть override → готовим копию inputs
    inputs2 = copy.deepcopy(inputs)
    prof2 = getattr(inputs2, "profile", None)
    if prof2:
        for k, v in profile_override.items():
            try:
                setattr(prof2, k, v)
            except Exception:
                pass

    # отключаем autosens/RT/temptarget
    try:
        inputs2.autosens.ratio = 1.0
    except Exception:
        pass

    try:
        inputs2.rt.sensitivityRatio = None
    except Exception:
        pass
    try:
        inputs2.rt.targetBG = None
    except Exception:
        pass

    try:
        inputs2.profile.autosens_adjust_targets = False
        inputs2.profile.sensitivity_raises_target = False
        inputs2.profile.resistance_lowers_target = False
        inputs2.profile.adv_target_adjustments = False
    except Exception:
        pass

    try:
        inputs2.profile.exercise_mode = False
    except Exception:
        pass

    try:
        inputs2.profile.temptargetSet = False
    except Exception:
        pass

    # кэш симуляций
    cache_key = _make_sim_cache_key(inputs2, profile_override)
    if cache_key is not None and cache_key in AUTOISF_SIM_CACHE:
        return AUTOISF_SIM_CACHE[cache_key]

    var_s, pred_s, dosing_s = run_autoisf_pipeline(inputs2)

    if cache_key is not None:
        AUTOISF_SIM_CACHE[cache_key] = (var_s, pred_s, dosing_s)

    return var_s, pred_s, dosing_s


def run_aps_what_if(blocks, load_inputs_before_fn, profile_override: Dict[str, Any]):
    """
    Чистая, быстрая версия APS‑what‑if с кэшированием оригинальных прогонов
    и симуляций с override.
    """
    pred_orig_all: List[float | None] = []
    pred_sim_all: List[float | None] = []
    ts_all: List[datetime | None] = []

    var_sens_orig: List[float | None] = []
    var_sens_sim: List[float | None] = []

    autoisf_orig: List[float | None] = []
    autoisf_sim: List[float | None] = []

    eventual_orig: List[float | None] = []
    eventual_sim: List[float | None] = []

    minpred_orig: List[float | None] = []
    minpred_sim: List[float | None] = []

    insulin_orig: List[float | None] = []
    insulin_sim: List[float | None] = []

    basal_orig: List[float | None] = []
    basal_sim: List[float | None] = []

    smb_orig: List[float | None] = []
    smb_sim: List[float | None] = []

    for idx, ts, block in blocks:
        inputs_before = load_inputs_before_fn(ts)

        try:
            inputs = build_inputs_from_block(block)
        except Exception:
            continue

        inputs = restore_inputs(inputs, inputs_before)

        # ORIGINAL with caching
        if ts in AUTOISF_CACHE:
            var_o, pred_o, dosing_o = AUTOISF_CACHE[ts]
        else:
            try:
                var_o, pred_o, dosing_o = run_autoisf_pipeline(inputs)
                AUTOISF_CACHE[ts] = (var_o, pred_o, dosing_o)
            except Exception:
                var_o = None
                pred_o = None
                dosing_o = None

        arr_o = extract_pred_array(pred_o)
        pred_orig_all.extend(arr_o)

        var_sens_orig.append(getattr(var_o, "variable_sens", None) if var_o else None)
        autoisf_orig.append(getattr(var_o, "autoISF_factor", None) if var_o else None)
        eventual_orig.append(getattr(pred_o, "eventualBG", None) if pred_o else None)
        minpred_orig.append(getattr(pred_o, "minPredBG", None) if pred_o else None)
        insulin_orig.append(getattr(dosing_o, "insulinReq", None) if dosing_o else None)
        basal_orig.append(getattr(dosing_o, "rate", None) if dosing_o else None)
        smb_orig.append(getattr(dosing_o, "smb", None) if dosing_o else None)

        # SIMULATION (с кэшем override)
        try:
            var_s, pred_s, dosing_s = _run_single(inputs, profile_override)
        except Exception:
            var_s = None
            pred_s = None
            dosing_s = None

        arr_s = extract_pred_array(pred_s)

        # выравниваем длину
        if len(arr_s) < len(arr_o):
            arr_s.extend([None] * (len(arr_o) - len(arr_s)))
        elif len(arr_s) > len(arr_o):
            arr_s = arr_s[: len(arr_o)]

        pred_sim_all.extend(arr_s)

        var_sens_sim.append(getattr(var_s, "variable_sens", None) if var_s else None)
        autoisf_sim.append(getattr(var_s, "autoISF_factor", None) if var_s else None)
        eventual_sim.append(getattr(pred_s, "eventualBG", None) if pred_s else None)
        minpred_sim.append(getattr(pred_s, "minPredBG", None) if pred_s else None)
        insulin_sim.append(getattr(dosing_s, "insulinReq", None) if dosing_s else None)
        basal_sim.append(getattr(dosing_s, "rate", None) if dosing_s else None)
        smb_sim.append(getattr(dosing_s, "smb", None) if dosing_s else None)

        # timestamps
        try:
            start_dt = datetime.fromtimestamp(ts / 1000.0)
        except Exception:
            start_dt = None

        for i in range(len(arr_o)):
            if start_dt:
                ts_all.append(start_dt + timedelta(minutes=5 * i))
            else:
                ts_all.append(None)

    return (
        pred_orig_all, pred_sim_all, ts_all,
        var_sens_orig, var_sens_sim,
        autoisf_orig, autoisf_sim,
        eventual_orig, eventual_sim,
        minpred_orig, minpred_sim,
        insulin_orig, insulin_sim,
        basal_orig, basal_sim,
        smb_orig, smb_sim,
    )
