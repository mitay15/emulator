# aaps_emulator/core/autoisf_pipeline.py
from __future__ import annotations

import logging

from aaps_emulator.core.autoisf_full import compute_variable_sens
from aaps_emulator.core.autoisf_structs import (
    AutosensResult,
    GlucoseStatusAutoIsf,
    IobTotal,
    MealData,
    OapsProfileAutoIsf,
    TempBasal,
    AutoIsfInputs,
)
from aaps_emulator.core.determine_basal import DosingResult, run_determine_basal
from aaps_emulator.core.predictions import PredictionsResult, run_predictions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# НОРМАЛИЗАЦИЯ ВХОДОВ
# ---------------------------------------------------------
def _ensure_dataclass(value, cls):
    if value is None or isinstance(value, cls):
        return value
    if isinstance(value, dict):
        return cls(**value)
    return value


def _normalize_glucose_status(gs: GlucoseStatusAutoIsf | None):
    if not gs:
        return gs
    for field in [
        "glucose",
        "delta",
        "shortAvgDelta",
        "longAvgDelta",
        "bgAcceleration",
        "corrSqu",
        "duraISFminutes",
        "duraISFaverage",
    ]:
        val = getattr(gs, field, None)
        if isinstance(val, str):
            try:
                setattr(gs, field, float(val))
            except Exception:
                setattr(gs, field, 0.0)
    return gs


def _normalize_profile(profile):
    if profile is None:
        return None

    # Если профиль — список, берём первый
    if isinstance(profile, list) and profile:
        profile = profile[0]

    # Если профиль — {"profile": {...}}
    if isinstance(profile, dict) and "profile" in profile:
        profile = profile["profile"]

    # Если профиль — dict → маппим в OapsProfileAutoIsf
    if isinstance(profile, dict):
        mapped = {
            "min_bg": profile.get("min_bg", profile.get("minBg")),
            "max_bg": profile.get("max_bg", profile.get("maxBg")),
            "target_bg": profile.get("target_bg"),
            "current_basal": profile.get("current_basal", profile.get("currentBasal")),
            "max_basal": profile.get("max_basal", profile.get("maxBasal")),
            "max_daily_basal": profile.get("max_daily_basal", profile.get("maxDailyBasal")),
            "max_daily_safety_multiplier": profile.get("max_daily_safety_multiplier"),
            "current_basal_safety_multiplier": profile.get("current_basal_safety_multiplier"),
            "sens": profile.get("sens", profile.get("isf")),
            "autosens_max": profile.get("autosens_max"),
            "autosens_min": profile.get("autosens_min"),
            "enable_autoISF": profile.get("enable_autoISF", True),
            "autoISF_min": profile.get("autoISF_min"),
            "autoISF_max": profile.get("autoISF_max"),
            "autoISF_version": profile.get("autoISF_version"),
            "bgAccel_ISF_weight": profile.get("bgAccel_ISF_weight"),
            "bgBrake_ISF_weight": profile.get("bgBrake_ISF_weight"),
            "pp_ISF_weight": profile.get("pp_ISF_weight"),
            "dura_ISF_weight": profile.get("dura_ISF_weight"),
            "lower_ISFrange_weight": profile.get("lower_ISFrange_weight"),
            "higher_ISFrange_weight": profile.get("higher_ISFrange_weight"),
            "carb_ratio": profile.get("carb_ratio", profile.get("ic")),
            "smb_delivery_ratio": profile.get("smb_delivery_ratio"),
            "smb_delivery_ratio_min": profile.get("smb_delivery_ratio_min"),
            "smb_delivery_ratio_max": profile.get("smb_delivery_ratio_max"),
            "bolus_increment": profile.get("bolus_increment"),
            "maxSMBBasalMinutes": profile.get("maxSMBBasalMinutes"),
            "maxUAMSMBBasalMinutes": profile.get("maxUAMSMBBasalMinutes"),
            "enableUAM": profile.get("enableUAM", False),
            "high_temptarget_raises_sensitivity": profile.get("high_temptarget_raises_sensitivity", False),
            "low_temptarget_lowers_sensitivity": profile.get("low_temptarget_lowers_sensitivity", False),
            "lgsThreshold": profile.get("lgsThreshold"),
            "max_iob": profile.get("max_iob"),
            "iob_threshold_percent": profile.get("iob_threshold_percent"),
            "half_basal_exercise_target": profile.get("half_basal_exercise_target"),
        }

        mapped_clean = {k: v for k, v in mapped.items() if v is not None}
        mapped_clean["raw"] = profile
        return OapsProfileAutoIsf(**mapped_clean)

    return profile


def _normalize_inputs(inputs: AutoIsfInputs) -> AutoIsfInputs:
    inputs.glucose_status = _ensure_dataclass(inputs.glucose_status, GlucoseStatusAutoIsf)
    inputs.profile = _ensure_dataclass(inputs.profile, OapsProfileAutoIsf)
    inputs.autosens = _ensure_dataclass(inputs.autosens, AutosensResult)
    inputs.meal = _ensure_dataclass(inputs.meal, MealData)
    inputs.current_temp = _ensure_dataclass(inputs.current_temp, TempBasal)

    if inputs.iob_data_array and isinstance(inputs.iob_data_array[0], dict):
        inputs.iob_data_array = [
            _ensure_dataclass(x, IobTotal) for x in inputs.iob_data_array
        ]

    inputs.glucose_status = _normalize_glucose_status(inputs.glucose_status)
    inputs.profile = _normalize_profile(inputs.profile)

    return inputs


# ---------------------------------------------------------
# ОСНОВНОЙ ПАЙПЛАЙН AUTOISF
# ---------------------------------------------------------
def run_autoisf_pipeline(inputs: AutoIsfInputs):
    inputs = _normalize_inputs(inputs)

    p = inputs.profile
    gs = inputs.glucose_status

    # fallback профиль
    if p is None:
        p = OapsProfileAutoIsf(
            min_bg=90,
            max_bg=110,
            sens=50,
            carb_ratio=10,
            current_basal=1.0,
            max_basal=3.0,
            max_daily_basal=3.0,
        )
        inputs.profile = p

    # autosens_ratio
    autosens_ratio = inputs.autosens.ratio if inputs.autosens else 1.0
    if p.autosens_max is not None:
        autosens_ratio = min(autosens_ratio, p.autosens_max)
    if p.autosens_min is not None:
        autosens_ratio = max(autosens_ratio, p.autosens_min)

    # Temp Targets
    tt = None
    rb = inputs.raw_block
    if isinstance(rb, dict):
        tt = rb.get("temptarget")
    elif isinstance(rb, list) and rb and isinstance(rb[0], dict):
        tt = rb[0].get("temptarget")

    if tt and tt.get("duration", 0) > 0:
        isTempTarget = True
        target_bg = tt.get(
            "target",
            p.target_bg or ((p.min_bg + p.max_bg) / 2.0 if p.min_bg and p.max_bg else None),
        )
    else:
        isTempTarget = False
        target_bg = p.target_bg or (
            (p.min_bg + p.max_bg) / 2.0 if p.min_bg and p.max_bg else None
        )

    normalTarget = (
        (p.min_bg + p.max_bg) / 2.0
        if p.min_bg is not None and p.max_bg is not None
        else target_bg
    )

    # AutoISF параметры
    autoISF_min = p.autoISF_min if p.autoISF_min is not None else 0.5
    autoISF_max = p.autoISF_max if p.autoISF_max is not None else 2.0

    bgAccel_weight = p.bgAccel_ISF_weight if p.bgAccel_ISF_weight is not None else 0.01
    bgBrake_weight = p.bgBrake_ISF_weight if p.bgBrake_ISF_weight is not None else 0.01
    pp_weight = p.pp_ISF_weight if p.pp_ISF_weight is not None else 0.01
    dura_weight = p.dura_ISF_weight if p.dura_ISF_weight is not None else 0.01
    lower_range_weight = p.lower_ISFrange_weight or 0.0
    higher_range_weight = p.higher_ISFrange_weight or 0.0

    high_tt = p.high_temptarget_raises_sensitivity if p.high_temptarget_raises_sensitivity is not None else True
    low_tt = p.low_temptarget_lowers_sensitivity if p.low_temptarget_lowers_sensitivity is not None else True

    # полный AutoISF
    variable_sens = compute_variable_sens(
        p,
        gs,
        autosens_ratio,
        autoISF_min,
        autoISF_max,
        bgAccel_weight,
        bgBrake_weight,
        pp_weight,
        dura_weight,
        lower_range_weight,
        higher_range_weight,
        target_bg,
        normalTarget,
        isTempTarget,
        high_tt,
        low_tt,
    )

    # fallback variable_sens
    try:
        if variable_sens is None or float(variable_sens) <= 0:
            if inputs.autosens and inputs.autosens.ratio and float(inputs.autosens.ratio) > 0:
                variable_sens = float(inputs.autosens.ratio)
            else:
                base = getattr(inputs.profile, "sens", None)
                variable_sens = float(base) if base and float(base) > 0 else 1.0
        else:
            variable_sens = float(variable_sens)
    except Exception:
        variable_sens = 1.0

    try:
        inputs.profile.variable_sens = variable_sens
    except Exception:
        pass

    # предсказания
    pred: PredictionsResult = run_predictions(inputs)

    # нормализация predBGs
    try:
        predBGs = {}
        if pred.pred_iob is not None:
            predBGs["IOB"] = list(pred.pred_iob)
        if pred.pred_uam is not None:
            predBGs["UAM"] = list(pred.pred_uam)
        if pred.pred_zt is not None:
            predBGs["ZT"] = list(pred.pred_zt)
        if predBGs:
            pred.predBGs = predBGs
    except Exception:
        pass

    # determine_basal
    dosing: DosingResult = run_determine_basal(
        inputs=inputs,
        pred=pred,
        variable_sens=variable_sens,
    )

    # AAPS-style aliases
    try:
        pred.eventualBG = getattr(pred, "eventual_bg", None)
        pred.minPredBG = getattr(pred, "min_pred_bg", None)
        pred.minGuardBG = getattr(pred, "min_guard_bg", None)
    except Exception:
        pass

    return variable_sens, pred, dosing
