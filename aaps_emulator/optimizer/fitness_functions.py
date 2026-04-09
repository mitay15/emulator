# aaps_emulator/optimizer/fitness_functions.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
import hashlib
import json

from aaps_emulator.core.autoisf_pipeline import run_autoisf_pipeline
from aaps_emulator.runner.build_inputs import build_inputs_from_block

from .utils import mae, filter_blocks_by_date
from .autoisf_internal import compute_autoisf_internal
from aaps_emulator.core.cache import FITNESS_CACHE

def _safe_float(value, default=0.0):
    """
    Преобразует value в float, но если value is None или преобразование не удалось,
    возвращает default (как float).
    """
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _apply_profile_to_inputs(inputs: Any, profile: Dict[str, Any]) -> Any:
    prof_obj = getattr(inputs, "profile", None)
    if prof_obj:
        for k, v in profile.items():
            try:
                setattr(prof_obj, k, v)
            except Exception:
                pass

    # отключаем autosens
    try:
        inputs.autosens.ratio = 1.0
    except Exception:
        pass

    # отключаем влияние RT на sens/target
    try:
        inputs.rt.sensitivityRatio = None
    except Exception:
        pass
    try:
        inputs.rt.targetBG = None
    except Exception:
        pass

    # отключаем target adjustments
    try:
        inputs.profile.autosens_adjust_targets = False
        inputs.profile.sensitivity_raises_target = False
        inputs.profile.resistance_lowers_target = False
        inputs.profile.adv_target_adjustments = False
    except Exception:
        pass

    # отключаем exercise mode
    try:
        inputs.profile.exercise_mode = False
    except Exception:
        pass

    # отключаем temptarget
    try:
        inputs.profile.temptargetSet = False
    except Exception:
        pass

    return inputs


def evaluate_profile_fitness(
    blocks: List[Tuple[int, int, List[dict]]],
    profile: Dict[str, Any],
    start_ts: Optional[int],
    end_ts: Optional[int],
) -> float:
    """
    Основная fitness-функция.
    Чем МЕНЬШЕ значение, тем ЛУЧШЕ профиль.
    """

    # ============================================================
    # 1. КЭШИРОВАНИЕ
    # ============================================================
    try:
        profile_key = hashlib.md5(
            json.dumps(profile, sort_keys=True).encode("utf-8")
        ).hexdigest()
    except Exception:
        profile_key = None

    fitness_key = (profile_key, start_ts, end_ts)

    if profile_key is not None and fitness_key in FITNESS_CACHE:
        return FITNESS_CACHE[fitness_key]

    # ============================================================
    # 2. ФИЛЬТРАЦИЯ БЛОКОВ
    # ============================================================
    filtered = filter_blocks_by_date(blocks, start_ts, end_ts)

    if not filtered:
        return 999.0  # мягкий штраф

    # Защищённые чтения ключевых числовых параметров профиля
    target_bg = _safe_float(profile.get("target_bg"), 100.0)
    max_smb = _safe_float(profile.get("maxSMBBasalMinutes"), 30.0)

    # Дополнительные числовые поля, которые могут понадобиться в будущем
    _ = _safe_float(profile.get("sens"), 100.0)
    _ = _safe_float(profile.get("current_basal"), 0.0)
    _ = _safe_float(profile.get("carb_ratio"), 10.0)
    _ = _safe_float(profile.get("max_iob"), 0.0)
    _ = _safe_float(profile.get("bolus_increment"), 0.1)
    _ = _safe_float(profile.get("smb_delivery_ratio"), 0.5)

    eventualBG_list: List[Optional[float]] = []
    minPredBG_list: List[Optional[float]] = []
    smb_list: List[Optional[float]] = []
    autoisf_factor_list: List[Optional[float]] = []
    var_sens_list: List[Optional[float]] = []

    # ============================================================
    # 3. ПРОГОН ВСЕХ БЛОКОВ
    # ============================================================
    for idx, ts, block_objs in filtered:
        try:
            inputs = build_inputs_from_block(block_objs)
        except Exception:
            continue

        inputs = _apply_profile_to_inputs(inputs, profile)

        try:
            var, pred, dosing = run_autoisf_pipeline(inputs)
        except Exception:
            continue

        # eventualBG
        try:
            v = getattr(pred, "eventualBG", None)
            eventualBG_list.append(float(v) if v is not None else None)
        except Exception:
            eventualBG_list.append(None)

        # minPredBG
        try:
            v = getattr(pred, "minPredBG", None)
            minPredBG_list.append(float(v) if v is not None else None)
        except Exception:
            minPredBG_list.append(None)

        # SMB
        try:
            v = getattr(dosing, "smb", None)
            smb_list.append(float(v) if v is not None else None)
        except Exception:
            smb_list.append(None)

        # AutoISF internal
        try:
            internal = compute_autoisf_internal(inputs, profile)
        except Exception:
            internal = None

        if internal is not None:
            # internal.autoISF_factor и internal.variable_sens уже числовые/None
            autoisf_factor_list.append(internal.autoISF_factor)
            var_sens_list.append(internal.variable_sens)
        else:
            autoisf_factor_list.append(None)
            var_sens_list.append(None)

    # ============================================================
    # 4. РАСЧЁТ FITNESS
    # ============================================================

    # 1) Ошибка eventualBG относительно target_bg
    ev_values = [x for x in eventualBG_list if x is not None]
    if ev_values:
        base_error = mae(ev_values, [target_bg] * len(ev_values))
    else:
        base_error = 50.0  # мягкий штраф

    # 2) Гипо (ограниченный штраф)
    hypo_penalty = sum(min((70 - v) ** 2, 400) for v in minPredBG_list if v is not None and v < 70)

    # 3) Гипер (ограниченный штраф)
    hyper_penalty = sum(min((v - 250) ** 2, 400) for v in eventualBG_list if v is not None and v > 250)

    # 4) SMB превышение
    smb_penalty = sum(min((v - max_smb) ** 2, 400) for v in smb_list if v is not None and v > max_smb)

    # 5) AutoISF min/max
    autoISF_min = _safe_float(profile.get("autoISF_min"), 0.7)
    autoISF_max = _safe_float(profile.get("autoISF_max"), 1.4)

    autoisf_penalty = 0.0
    for v in autoisf_factor_list:
        if v is None:
            continue
        if v < autoISF_min:
            autoisf_penalty += min((autoISF_min - v) ** 2, 400)
        if v > autoISF_max:
            autoisf_penalty += min((v - autoISF_max) ** 2, 400)

    # 6) variable_sens стабильность
    var_sens_values = [v for v in var_sens_list if v is not None]
    if len(var_sens_values) > 1:
        mean_vs = sum(var_sens_values) / len(var_sens_values)
        var_sens_penalty = sum(min((v - mean_vs) ** 2, 400) for v in var_sens_values) / len(var_sens_values)
    else:
        var_sens_penalty = 0.0

    # Итоговый fitness
    fitness = float(
        base_error
        + 0.01 * hypo_penalty
        + 0.005 * hyper_penalty
        + 0.001 * smb_penalty
        + 0.01 * autoisf_penalty
        + 0.01 * var_sens_penalty
    )

    # ============================================================
    # 5. КЭШИРОВАНИЕ
    # ============================================================
    if profile_key is not None:
        FITNESS_CACHE[fitness_key] = fitness

    return fitness
