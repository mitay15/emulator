# aaps_emulator/optimizer/autoisf_internal.py
from __future__ import annotations
from typing import Dict, Any, Optional


class AutoISFResult:
    """
    Контейнер для всех внутренних переменных AutoISF.
    Используется оптимизатором и fitness-функциями.
    """
    def __init__(
        self,
        bg_off: float,
        bgAccel: float,
        bgBrake: float,
        pp: float,
        dura: float,
        lower_range: float,
        higher_range: float,
        weighted_sum: float,
        autoISF_factor: float,
        variable_sens: float
    ):
        self.bg_off = bg_off
        self.bgAccel = bgAccel
        self.bgBrake = bgBrake
        self.pp = pp
        self.dura = dura
        self.lower_range = lower_range
        self.higher_range = higher_range
        self.weighted_sum = weighted_sum
        self.autoISF_factor = autoISF_factor
        self.variable_sens = variable_sens


# ============================================================
# INTERNAL AUTOISF CALCULATION
# ============================================================

def compute_autoisf_internal(
    inputs: Any,
    profile: Dict[str, Any]
) -> Optional[AutoISFResult]:
    """
    Пересчитывает внутренние переменные AutoISF.
    Это Python-аналог логики AAPS (Kotlin).
    """

    # --------------------------------------------------------
    # 0) Проверяем наличие glucose_status / meal / rt
    # --------------------------------------------------------
    try:
        gs = inputs.glucose_status
        meal = inputs.meal
    except Exception:
        return None

    # --------------------------------------------------------
    # 1) bg_off — отклонение BG от target
    # --------------------------------------------------------
    try:
        bg = float(gs.glucose)
    except Exception:
        return None

    target_bg = float(profile.get("target_bg") or 100.0)
    bg_off = bg - target_bg

    # --------------------------------------------------------
    # 2) bgAccel — ускорение BG (вторая производная)
    # --------------------------------------------------------
    try:
        delta = float(gs.delta)
    except Exception:
        delta = 0.0

    try:
        prevDelta = float(gs.prevDelta)
    except Exception:
        prevDelta = 0.0

    bgAccel = delta - prevDelta
    bgBrake = -bgAccel

    # --------------------------------------------------------
    # 3) pp — postprandial
    # --------------------------------------------------------
    try:
        pp = float(meal.slopeFromMaxDeviation)
    except Exception:
        pp = 0.0

    # --------------------------------------------------------
    # 4) dura — длительность действия углеводов
    # --------------------------------------------------------
    try:
        dura = float(meal.slopeFromMinDeviation)
    except Exception:
        dura = 0.0

    # --------------------------------------------------------
    # 5) lower/higher ISF range
    # --------------------------------------------------------
    def _safe(v):
        try:
            return float(v)
        except Exception:
            return 0.0

    lower_range = _safe(profile.get("lower_ISFrange_weight"))
    higher_range = _safe(profile.get("higher_ISFrange_weight"))

    # --------------------------------------------------------
    # 6) Weights
    # --------------------------------------------------------
    w_accel = float(profile.get("bgAccel_ISF_weight") or 0.0)
    w_brake = float(profile.get("bgBrake_ISF_weight") or 0.0)
    w_pp = float(profile.get("pp_ISF_weight") or 0.0)
    w_dura = float(profile.get("dura_ISF_weight") or 0.0)

    # --------------------------------------------------------
    # 7) Weighted sum
    # --------------------------------------------------------
    weighted_sum = (
        bgAccel * w_accel +
        bgBrake * w_brake +
        pp * w_pp +
        dura * w_dura +
        lower_range +
        higher_range
    )

    # --------------------------------------------------------
    # 8) AutoISF factor
    # --------------------------------------------------------
    autoISF_min = float(profile.get("autoISF_min") or 0.7)
    autoISF_max = float(profile.get("autoISF_max") or 1.4)

    # clamp
    autoISF_factor = weighted_sum
    if autoISF_factor < autoISF_min:
        autoISF_factor = autoISF_min
    if autoISF_factor > autoISF_max:
        autoISF_factor = autoISF_max

    # --------------------------------------------------------
    # 9) variable_sens = sens / autoISF_factor
    # --------------------------------------------------------
    sens = float(profile.get("sens") or 45.0)

    if autoISF_factor == 0:
        variable_sens = sens
    else:
        variable_sens = sens / autoISF_factor

    # --------------------------------------------------------
    # 10) Возвращаем результат
    # --------------------------------------------------------
    return AutoISFResult(
        bg_off=bg_off,
        bgAccel=bgAccel,
        bgBrake=bgBrake,
        pp=pp,
        dura=dura,
        lower_range=lower_range,
        higher_range=higher_range,
        weighted_sum=weighted_sum,
        autoISF_factor=autoISF_factor,
        variable_sens=variable_sens
    )
