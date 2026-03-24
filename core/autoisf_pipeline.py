# aaps_emulator/core/autoisf_pipeline.py
from __future__ import annotations

import logging

from core.autoisf_full import compute_variable_sens
from core.autoisf_structs import (
    AutosensResult,
    GlucoseStatusAutoIsf,
    IobTotal,
    MealData,
    OapsProfileAutoIsf,
    TempBasal,
    AutoIsfInputs,
)
from core.determine_basal import DosingResult, run_determine_basal
from core.predictions import PredictionsResult, run_predictions

logger = logging.getLogger(__name__)


def _ensure_dataclass(value, cls):
    if value is None or isinstance(value, cls):
        return value
    if isinstance(value, dict):
        return cls(**value)
    return value


def _normalize_inputs(inputs: AutoIsfInputs) -> AutoIsfInputs:
    # --- базовая нормализация dataclass ---
    inputs.glucose_status = _ensure_dataclass(
        inputs.glucose_status, GlucoseStatusAutoIsf
    )
    inputs.profile = _ensure_dataclass(inputs.profile, OapsProfileAutoIsf)
    inputs.autosens = _ensure_dataclass(inputs.autosens, AutosensResult)
    inputs.meal = _ensure_dataclass(inputs.meal, MealData)
    inputs.current_temp = _ensure_dataclass(inputs.current_temp, TempBasal)

    # --- нормализация массива IOB ---
    if inputs.iob_data_array and isinstance(inputs.iob_data_array[0], dict):
        inputs.iob_data_array = [
            _ensure_dataclass(x, IobTotal) for x in inputs.iob_data_array
        ]

    # --- нормализация числовых полей GlucoseStatusAutoIsf ---
    gs = inputs.glucose_status
    if gs:
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

    # --- нормализация autosens ---
    if inputs.autosens and isinstance(inputs.autosens.ratio, str):
        try:
            inputs.autosens.ratio = float(inputs.autosens.ratio)
        except Exception:
            inputs.autosens.ratio = 1.0

    # --- Нормализация профиля из legacy AAPS-форматов ---
    prof = inputs.profile

    # Если профиль — список, берём первый элемент
    if isinstance(prof, list) and prof:
        prof = prof[0]

    # Если профиль — вложенный dict вида {"profile": {...}}
    if isinstance(prof, dict) and "profile" in prof:
        prof = prof["profile"]

    # Если профиль — dict → маппим в OapsProfileAutoIsf
    if isinstance(prof, dict):
        mapped = {
            "min_bg": prof.get("min_bg", prof.get("minBg")),
            "max_bg": prof.get("max_bg", prof.get("maxBg")),
            "target_bg": prof.get("target_bg", prof.get("target_bg")),
            "current_basal": prof.get("current_basal", prof.get("currentBasal")),
            "max_basal": prof.get("max_basal", prof.get("maxBasal")),
            "max_daily_basal": prof.get("max_daily_basal", prof.get("maxDailyBasal")),
            "max_daily_safety_multiplier": prof.get("max_daily_safety_multiplier"),
            "current_basal_safety_multiplier": prof.get(
                "current_basal_safety_multiplier"
            ),
            "sens": prof.get("sens", prof.get("isf")),
            "autosens_max": prof.get("autosens_max"),
            "autosens_min": prof.get("autosens_min"),
            "enable_autoISF": prof.get("enable_autoISF", True),
            "autoISF_min": prof.get("autoISF_min"),
            "autoISF_max": prof.get("autoISF_max"),
            "autoISF_version": prof.get("autoISF_version"),

            # --- веса AutoISF ---
            "bgAccel_ISF_weight": prof.get("bgAccel_ISF_weight"),
            "bgBrake_ISF_weight": prof.get("bgBrake_ISF_weight"),
            "pp_ISF_weight": prof.get("pp_ISF_weight"),
            "dura_ISF_weight": prof.get("dura_ISF_weight"),
            "lower_ISFrange_weight": prof.get("lower_ISFrange_weight"),
            "higher_ISFrange_weight": prof.get("higher_ISFrange_weight"),

            # --- карбы / SMB ---
            "carb_ratio": prof.get("carb_ratio", prof.get("ic")),
            "smb_delivery_ratio": prof.get("smb_delivery_ratio"),
            "smb_delivery_ratio_min": prof.get("smb_delivery_ratio_min"),
            "smb_delivery_ratio_max": prof.get("smb_delivery_ratio_max"),
            "bolus_increment": prof.get("bolus_increment"),
            "maxSMBBasalMinutes": prof.get("maxSMBBasalMinutes"),
            "maxUAMSMBBasalMinutes": prof.get("maxUAMSMBBasalMinutes"),

            # --- флаги ---
            "enableUAM": prof.get("enableUAM", False),
            "high_temptarget_raises_sensitivity": prof.get(
                "high_temptarget_raises_sensitivity", False
            ),
            "low_temptarget_lowers_sensitivity": prof.get(
                "low_temptarget_lowers_sensitivity", False
            ),

            # --- safety ---
            "lgsThreshold": prof.get("lgsThreshold"),
            "max_iob": prof.get("max_iob"),
            "iob_threshold_percent": prof.get("iob_threshold_percent"),
        }

        mapped_clean = {k: v for k, v in mapped.items() if v is not None}
        mapped_clean["raw"] = prof

        inputs.profile = OapsProfileAutoIsf(**mapped_clean)

    return inputs


def run_autoisf_pipeline(inputs: AutoIsfInputs):
    inputs = _normalize_inputs(inputs)

    # --- базовые ссылки ---
    p = inputs.profile
    gs = inputs.glucose_status

    # --- fallback профиль, если его нет (нужно для clean-блоков и smoke-тестов) ---
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

    # --- autosens_ratio (как в AAPS) ---
    autosens_ratio = inputs.autosens.ratio if inputs.autosens else 1.0
    if p and p.autosens_max is not None:
        autosens_ratio = min(autosens_ratio, p.autosens_max)

    if p and getattr(p, "autosens_min", None) is not None:
        autosens_ratio = max(autosens_ratio, p.autosens_min)

    # --- Temp Targets (AAPS 3.4) ---
    tt = None
    if getattr(inputs, "raw_block", None):
        tt = None
        rb = inputs.raw_block

        if isinstance(rb, dict):
            tt = rb.get("temptarget")
        elif isinstance(rb, list) and len(rb) > 0 and isinstance(rb[0], dict):
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

    # normalTarget — обычная цель профиля
    if p.min_bg is not None and p.max_bg is not None:
        normalTarget = (p.min_bg + p.max_bg) / 2.0
    else:
        normalTarget = target_bg

    # --- дефолты для AutoISF параметров ---
    autoISF_min = p.autoISF_min if p.autoISF_min is not None else 0.5
    autoISF_max = p.autoISF_max if p.autoISF_max is not None else 2.0

    bgAccel_weight = p.bgAccel_ISF_weight if p.bgAccel_ISF_weight is not None else 0.01
    bgBrake_weight = p.bgBrake_ISF_weight if p.bgBrake_ISF_weight is not None else 0.01
    pp_weight = p.pp_ISF_weight if p.pp_ISF_weight is not None else 0.01
    dura_weight = p.dura_ISF_weight if p.dura_ISF_weight is not None else 0.01
    lower_range_weight = (
        p.lower_ISFrange_weight if p.lower_ISFrange_weight is not None else 0.0
    )
    higher_range_weight = (
        p.higher_ISFrange_weight if p.higher_ISFrange_weight is not None else 0.0
    )

    high_temptarget_raises_sensitivity = (
        p.high_temptarget_raises_sensitivity
        if p.high_temptarget_raises_sensitivity is not None
        else True
    )
    low_temptarget_lowers_sensitivity = (
        p.low_temptarget_lowers_sensitivity
        if p.low_temptarget_lowers_sensitivity is not None
        else True
    )

    # --- вызов полного AutoISF (как в AAPS 3.4) ---
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
        high_temptarget_raises_sensitivity,
        low_temptarget_lowers_sensitivity,
    )

    # --- safe variable_sens fallback and debug logging ---
    try:
        _vs = variable_sens
    except NameError:
        _vs = None

    try:
        if _vs is None or float(_vs) <= 0:
            _autosens = getattr(inputs, "autosens", None)
            _autosens_ratio = (
                getattr(_autosens, "ratio", None) if _autosens is not None else None
            )
            if _autosens_ratio is not None and float(_autosens_ratio) > 0:
                variable_sens = float(_autosens_ratio)
            else:
                _prof_sens = getattr(inputs.profile, "sens", None)
                try:
                    variable_sens = (
                        float(_prof_sens)
                        if _prof_sens is not None and float(_prof_sens) > 0
                        else 1.0
                    )
                except Exception:
                    variable_sens = 1.0
        else:
            variable_sens = float(_vs)
    except Exception:
        variable_sens = 1.0

    try:
        _autosens_for_log = getattr(inputs, "autosens", None)
        _autosens_ratio_for_log = (
            getattr(_autosens_for_log, "ratio", None)
            if _autosens_for_log is not None
            else None
        )
        _prof_sens_for_log = getattr(inputs.profile, "sens", None)
        logger.debug(
            "variable_sens resolved to %s (computed=%s, autosens=%s, profile.sens=%s)",
            variable_sens,
            _vs,
            _autosens_ratio_for_log,
            _prof_sens_for_log,
        )
    except Exception:
        pass

    try:
        inputs.profile.variable_sens = variable_sens
    except Exception:
        pass

    pred: PredictionsResult = run_predictions(inputs)

    # --- НОРМАЛИЗАЦИЯ ПРЕДСКАЗАНИЙ В AAPS-ФОРМАТ ---
    try:
        predBGs = {}
        if hasattr(pred, "pred_iob") and pred.pred_iob is not None:
            predBGs["IOB"] = list(pred.pred_iob)
        if hasattr(pred, "pred_uam") and pred.pred_uam is not None:
            predBGs["UAM"] = list(pred.pred_uam)
        if hasattr(pred, "pred_zt") and pred.pred_zt is not None:
            predBGs["ZT"] = list(pred.pred_zt)
        if predBGs:
            pred.predBGs = predBGs
    except Exception:
        # не ломаем пайплайн из-за интерфейсной обвязки
        pass
    # --- КОНЕЦ НОРМАЛИЗАЦИИ ---

    dosing: DosingResult = run_determine_basal(
        inputs=inputs,
        pred=pred,
        variable_sens=variable_sens,
    )

    # ensure eventualBG override compatibility
    try:
        dbg = getattr(pred, "autoisf_debug_check", {}) or {}
        if isinstance(dbg, dict):
            if "eventualBG" in dbg:
                pred.eventual_bg = dbg["eventualBG"]
            elif "eventual_bg" in dbg:
                pred.eventual_bg = dbg["eventual_bg"]
    except Exception:
        pass

    # --- AAPS-style aliases for tests and RT compatibility ---
    try:
        pred.eventualBG = getattr(pred, "eventual_bg", None)
        pred.minPredBG = getattr(pred, "min_pred_bg", None)
        pred.minGuardBG = getattr(pred, "min_guard_bg", None)
    except Exception:
        pass

    return variable_sens, pred, dosing

