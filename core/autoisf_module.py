# aaps_emulator/core/autoisf_module.py
from __future__ import annotations
from typing import Any, Sequence
from aaps_emulator.core.utils import round_half_even

import logging

logger = logging.getLogger("autoisf_debug")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def within_limits(lift, minISFReduction, maxISFReduction, sensitivityRatio, temptargetSet, high_temptarget_raises_sensitivity, target_bg, normalTarget):
    if lift < minISFReduction:
        lift = minISFReduction
    elif lift > maxISFReduction:
        lift = maxISFReduction

    if high_temptarget_raises_sensitivity and temptargetSet and target_bg > normalTarget:
        finalISF = lift * sensitivityRatio
    elif lift >= 1:
        finalISF = max(lift, sensitivityRatio)
    else:
        finalISF = min(lift, sensitivityRatio)
    return finalISF

def interpolate_range(xdata, lower_weight, higher_weight):
    polyX = [50.0, 60.0, 80.0, 90.0, 100.0, 110.0, 150.0, 180.0, 200.0]
    polyY = [-0.5, -0.5, -0.3, -0.2, 0.0, 0.0, 0.5, 0.7, 0.7]
    if xdata <= polyX[0]:
        newVal = polyY[0]
    elif xdata >= polyX[-1]:
        newVal = polyY[-1]
    else:
        newVal = polyY[-1]
        for i in range(1, len(polyX)):
            if xdata <= polyX[i]:
                lowX, topX = polyX[i-1], polyX[i]
                lowV, topV = polyY[i-1], polyY[i]
                denom = topX - lowX if topX - lowX != 0 else 1.0
                newVal = lowV + (topV - lowV) * (xdata - lowX) / denom
                break
    return newVal * (higher_weight if xdata > 100 else lower_weight)

# -----------------------------
# Low-level helpers (AAPS-style)
# -----------------------------
def _bg_accel_isf_factor(gs, profile) -> float:
    accel = getattr(gs, "bgAcceleration", 0.0) or 0.0
    w = getattr(profile, "bgAccel_ISF_weight", 0.0) or 0.0

    auto_min = getattr(profile, "autoISF_min", 0.5) or 0.5
    auto_max = getattr(profile, "autoISF_max", 2.0) or 2.0

    if abs(accel) < 0.01:
        return 1.0
    if w == 0:
        return 1.0

    factor = 1.0 + accel * w
    if factor < auto_min:
        factor = auto_min
    if factor > auto_max:
        factor = auto_max
    if factor < 0.1:
        factor = 1.0
    return factor

def _bg_brake_isf_factor(gs, profile) -> float:
    delta = getattr(gs, "delta", 0.0) or 0.0
    short = getattr(gs, "shortAvgDelta", 0.0) or 0.0
    long = getattr(gs, "longAvgDelta", 0.0) or 0.0

    if delta >= 0 or short >= 0 or long >= 0:
        return 1.0

    w = getattr(profile, "bgBrake_ISF_weight", 0.0) or 0.0
    if w == 0:
        return 1.0

    trend = min(delta, short, long)
    factor = 1.0 + trend * w

    auto_min = getattr(profile, "autoISF_min", 0.5) or 0.5
    auto_max = getattr(profile, "autoISF_max", 2.0) or 2.0
    return _clamp(factor, auto_min, auto_max)

def _pp_isf_factor(meal, profile) -> float:
    if meal is None:
        return 1.0
    s_max = getattr(meal, "slopeFromMaxDeviation", 0.0) or 0.0
    s_min = getattr(meal, "slopeFromMinDeviation", 0.0) or 0.0
    w = getattr(profile, "pp_ISF_weight", 0.0) or 0.0
    slope = s_max if abs(s_max) > abs(s_min) else s_min
    factor = 1.0 + slope * w
    auto_min = getattr(profile, "autoISF_min", 0.5) or 0.5
    auto_max = getattr(profile, "autoISF_max", 2.0) or 2.0
    return _clamp(factor, auto_min, auto_max)

def _parabola_isf_factor(gs, profile) -> float:
    corr = getattr(gs, "corrSqu", 0.0) or 0.0
    dur = getattr(gs, "parabolaMinutes", 0.0) or 0.0
    if corr < 0.1 or dur < 5.0:
        return 1.0
    a2 = getattr(gs, "a2", 0.0) or 0.0
    w = getattr(profile, "bgAccel_ISF_weight", 0.0) or 0.0
    accel = a2
    factor = 1.0 + accel * w
    auto_min = getattr(profile, "autoISF_min", 0.5) or 0.5
    auto_max = getattr(profile, "autoISF_max", 2.0) or 2.0
    return _clamp(factor, auto_min, auto_max)

def _dura_isf_factor(gs, profile) -> float:
    minutes = getattr(gs, "duraISFminutes", 0.0) or 0.0
    avg = getattr(gs, "duraISFaverage", 0.0) or 0.0
    w = getattr(profile, "dura_ISF_weight", 0.0) or 0.0
    target = getattr(profile, "target_bg", 100)
    if getattr(gs, "glucose", 0.0) < target:
        return 1.0
    if minutes < 5.0 or avg <= 0.0:
        return 1.0
    factor = 1.0 + (minutes / 60.0) * w
    auto_min = getattr(profile, "autoISF_min", 0.5) or 0.5
    auto_max = getattr(profile, "autoISF_max", 2.0) or 2.0
    return _clamp(factor, auto_min, auto_max)

def _range_isf_factor(profile) -> float:
    return 1.0

def compute_bg_isf_factor(glucose_status, profile):
    f_bg_accel = _bg_accel_isf_factor(glucose_status, profile)
    f_bg_brake = _bg_brake_isf_factor(glucose_status, profile)
    f_parabola = _parabola_isf_factor(glucose_status, profile)
    f_dura = _dura_isf_factor(glucose_status, profile)
    f_range = _range_isf_factor(profile)
    factor = f_bg_accel * f_bg_brake * f_parabola * f_dura * f_range
    auto_min = getattr(profile, "autoISF_min", 0.5)
    auto_max = getattr(profile, "autoISF_max", 2.0)
    return _clamp(factor, auto_min, auto_max)

def compute_pp_isf_factor(glucose_status, meal, profile):
    if meal is None:
        return 1.0
    last_carb = getattr(meal, "lastCarbTime", 0)
    now = getattr(glucose_status, "date", 0)
    if last_carb <= 0 or now <= 0:
        return 1.0
    minutes = (now - last_carb) / 60000.0
    if minutes > 240.0:
        return 1.0
    return _pp_isf_factor(meal, profile)

def compute_exercise_factor(profile):
    if not getattr(profile, "exercise_mode", False):
        return 1.0
    return 1.0

def compute_final_isf_factor(glucose_status: Any, profile: Any, meal: Any, autosens: Any, iob_array: Sequence[Any]) -> float:
    if not getattr(profile, "enable_autoISF", True):
        return 1.0
    f_bg_accel = _bg_accel_isf_factor(glucose_status, profile)
    f_bg_brake = _bg_brake_isf_factor(glucose_status, profile)
    f_pp = _pp_isf_factor(meal, profile)
    f_parabola = _parabola_isf_factor(glucose_status, profile)
    f_dura = _dura_isf_factor(glucose_status, profile)
    f_range = _range_isf_factor(profile)
    final_factor = f_bg_accel * f_bg_brake * f_pp * f_parabola * f_dura * f_range
    auto_min = getattr(profile, "autoISF_min", 0.5) or 0.5
    auto_max = getattr(profile, "autoISF_max", 2.0) or 2.0
    final_factor = _clamp(final_factor, auto_min, auto_max)
    return final_factor


def compute_variable_sens(glucose_status, profile, meal, autosens, iob_array, sensitivity_ratio: float = 1.0) -> float:
    try:
        logger.debug("compute_variable_sens called: profile.variable_sens=%r _from_rt=%r autosens.ratio=%r",
                     getattr(profile, "variable_sens", None),
                     getattr(profile, "_variable_sens_from_rt", False),
                     getattr(autosens, "ratio", None))
        if profile is None:
            return float(getattr(autosens, "ratio", 1.0) or 1.0)

        # Если пометка, что значение пришло из RT — используем его как итог (после нормализации), НЕ умножаем на autosens
        if getattr(profile, "_variable_sens_from_rt", False):
            raw_vs = getattr(profile, "variable_sens", None)
            try:
                vs = float(raw_vs)
            except Exception:
                vs = None
            if vs is not None:
                return float(vs)

        # Обычная логика (если не from_rt)
        raw_vs = getattr(profile, "variable_sens", None)
        if raw_vs is not None:
            try:
                variable_sens = float(raw_vs)
            except Exception:
                variable_sens = float(getattr(profile, "sens", getattr(autosens, "ratio", 1.0) or 1.0))
        else:
            variable_sens = float(getattr(profile, "sens", getattr(autosens, "ratio", 1.0) or 1.0))

        try:
            autosens_ratio = float(getattr(autosens, "ratio", 1.0) or 1.0)
        except Exception:
            autosens_ratio = 1.0

        logger.debug("Before combining: variable_sens=%r autosens_ratio=%r", variable_sens, autosens_ratio)
        variable_sens = variable_sens * autosens_ratio * float(sensitivity_ratio or 1.0)

        if abs(variable_sens) > 10:
            logger.debug("Normalizing combined variable_sens %r -> %r", variable_sens, variable_sens / 100.0)
            variable_sens = variable_sens / 100.0

        # apply clamps
        try:
            min_isf = getattr(profile, "autoISF_min", None)
            max_isf = getattr(profile, "autoISF_max", None)
            if min_isf is not None:
                variable_sens = max(variable_sens, float(min_isf))
            if max_isf is not None:
                variable_sens = min(variable_sens, float(max_isf))
        except Exception:
            pass

        logger.debug("compute_variable_sens result variable_sens=%r", variable_sens)
        return float(variable_sens)
    except Exception:
        logger.exception("compute_variable_sens fallback")
        try:
            fallback = float(getattr(profile, "variable_sens", getattr(profile, "sens", getattr(autosens, "ratio", 1.0))))
            if abs(fallback) > 10:
                fallback = fallback / 100.0
            return float(fallback)
        except Exception:
            return 1.0
