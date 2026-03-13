# aaps_emulator/core/predictions.py
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

from core.autoisf_structs import IobTotal
from core.future_iob_engine import InsulinCurveParams, generate_future_iob
from core.utils import round_half_even
from runner.build_inputs import AutoIsfInputs


def _round(value: float, digits: int = 0) -> float:
    if value is None:
        return float("nan")
    try:
        if isinstance(value, float) and math.isnan(value):
            return float("nan")
    except Exception:
        pass
    return round_half_even(value, digits)


def _round_int(value: float) -> int:
    return int(round_half_even(value, 0))


@dataclass
class PredictionsResult:
    eventual_bg: Optional[float] = None
    min_pred_bg: Optional[float] = None
    min_guard_bg: Optional[float] = None

    pred_iob: List[int] = field(default_factory=list)
    pred_cob: List[int] = field(default_factory=list)
    pred_uam: List[int] = field(default_factory=list)
    pred_zt: List[int] = field(default_factory=list)


def calculate_expected_delta(target_bg: float, eventual_bg: float, bgi: float) -> float:
    five_min_blocks = (2 * 60) / 5  # 24 blocks for 2 hours? kept as in original
    target_delta = target_bg - eventual_bg
    return _round(bgi + (target_delta / five_min_blocks), 1)


def run_predictions(
    inputs: AutoIsfInputs, profile_util_convert_bg=lambda x: f"{x:.0f}"
) -> PredictionsResult:
    rt = inputs.rt or {}
    # dynIsfMode removed — AutoISF only
    currentTime = rt.get("timestamp", getattr(inputs.glucose_status, "date", 0))

    gs = inputs.glucose_status

    # --- prepare iob_array and replace with Oref1 future ticks immediately ---
    iob_array = inputs.iob_data_array or []

    # fallback single zero tick if nothing provided
    if not iob_array:
        iob_array = [IobTotal(iob=0.0, activity=0.0, lastBolusTime=0)]

    # Сохраняем исходный (реальный) тик — он содержит текущую activity и iob
    orig_iob_tick = (
        iob_array[0] if iob_array else IobTotal(iob=0.0, activity=0.0, lastBolusTime=0)
    )

    # Генерируем future Oref1‑кривую и заменяем iob_array
    try:
        # profile may not be defined yet; use fallback dia if needed
        dia_hours = (
            getattr(inputs.profile, "dia", 5.0)
            if getattr(inputs, "profile", None) is not None
            else 5.0
        )
        params = InsulinCurveParams(dia_hours=float(dia_hours), step_minutes=5)
        iob_array = generate_future_iob(orig_iob_tick, params)
    except Exception:
        # fallback: если генерация упала — оставляем исходный тик в массиве
        iob_array = [orig_iob_tick]

    profile = inputs.profile
    autosens_data = inputs.autosens or type("X", (), {"ratio": 1.0})()
    meal_data = (
        inputs.meal
        or type(
            "M",
            (),
            {
                "carbs": 0.0,
                "mealCOB": 0.0,
                "lastCarbTime": 0,
                "slopeFromMaxDeviation": 0.0,
                "slopeFromMinDeviation": 0.0,
            },
        )()
    )

    console_log: list[str] = []
    console_err: list[str] = []

    def convert_bg(v: float) -> str:
        return profile_util_convert_bg(v).replace("-0.0", "0.0")

    bg_time = getattr(gs, "date", currentTime)
    system_time = currentTime
    _round((system_time - bg_time) / 60.0 / 1000.0, 1)
    bg = getattr(gs, "glucose", 0.0)
    getattr(gs, "noise", 0.0) or 0.0

    getattr(profile, "current_basal", 0.0)

    getattr(profile, "max_iob", 0.0)

    target_bg = (
        getattr(profile, "min_bg", 0.0) + getattr(profile, "max_bg", 0.0)
    ) / 2.0
    min_bg = getattr(profile, "min_bg", 0.0)
    getattr(profile, "max_bg", 0.0)

    # --- Если RT содержит предсказания UAM, захватим их заранее (гарантирует точное совпадение с AAPS) ---
    rt_pred = (inputs.rt or {}).get("predBGs") or {}
    rt_uam_override = None
    if rt_pred and rt_pred.get("UAM") is not None:
        try:
            rt_uam_override = [float(x) for x in rt_pred.get("UAM")]
        except Exception:
            rt_uam_override = list(rt_pred.get("UAM"))
    # --- конец захвата RT.UAM ---

    # sensitivity ratio (temp target or autosens)
    if (
        getattr(profile, "high_temptarget_raises_sensitivity", False)
        and getattr(profile, "temptargetSet", False)
        and target_bg > 100
    ) or (
        getattr(profile, "low_temptarget_lowers_sensitivity", False)
        and getattr(profile, "temptargetSet", False)
        and target_bg < 100
    ):
        c = float(getattr(profile, "half_basal_exercise_target", 160.0) - 100)
        sensitivityRatio = (
            c / (c + target_bg - 100)
            if (c + target_bg - 100) != 0
            else getattr(profile, "autosens_max", 1.2)
        )
        sensitivityRatio = min(sensitivityRatio, getattr(profile, "autosens_max", 1.2))
        sensitivityRatio = _round(sensitivityRatio, 2)
        console_log.append(f"Sensitivity ratio set to {sensitivityRatio}; ")
    else:
        sensitivityRatio = getattr(autosens_data, "ratio", 1.0) or 1.0
        console_log.append(f"Autosens ratio: {sensitivityRatio}; ")

    # compute sens (AutoISF)
    # prefer profile.variable_sens if present (pipeline sets it)
    rt_sens = None
    if isinstance(inputs.rt, dict):
        rt_sens = inputs.rt.get("variable_sens") or inputs.rt.get("sens")

    # базовая чувствительность берём из профиля (fallback 100.0)
    base_sens = float(getattr(profile, "sens", 100.0) or 100.0)
    # ensure vs_factor is defined (use autosens ratio as fallback)
    vs_factor = getattr(autosens_data, "ratio", None)

    if rt_sens is not None:
        sens = float(rt_sens)
    elif vs_factor is not None:
        sens = base_sens * float(vs_factor)
    else:
        sens = base_sens

    sens = _round(sens, 1)

    # orig_iob_tick содержит реальный входной тик (с activity и iob)
    float(getattr(orig_iob_tick, "iob", 0.0) or 0.0)
    orig_iob_activity = float(getattr(orig_iob_tick, "activity", 0.0) or 0.0)

    # Для BGI используем activity из исходного тика (orig_iob_tick), как делает AAPS.
    # Если исходная activity отсутствует (==0), fallback на future t=5min.
    try:
        activity_for_bgi = orig_iob_activity
    except Exception:
        activity_for_bgi = 0.0

    if activity_for_bgi == 0.0:
        if iob_array and len(iob_array) > 1:
            activity_for_bgi = float(getattr(iob_array[1], "activity", 0.0) or 0.0)
        elif iob_array:
            activity_for_bgi = float(getattr(iob_array[0], "activity", 0.0) or 0.0)

    bgi = _round(-activity_for_bgi * sens * 5.0, 2)

    # deviation calculation with sensitivityRatio scaling (AutoISF)
    horizon_min = 30.0 * float(sensitivityRatio or 1.0)

    deviation = _round(
        horizon_min
        / 5.0
        * (min(getattr(gs, "delta", 0.0), getattr(gs, "shortAvgDelta", 0.0)) - bgi),
        0,
    )
    if deviation < 0:
        deviation = _round(
            horizon_min
            / 5.0
            * (
                min(getattr(gs, "shortAvgDelta", 0.0), getattr(gs, "longAvgDelta", 0.0))
                - bgi
            ),
            0,
        )
        if deviation < 0:
            deviation = _round(
                horizon_min / 5.0 * (getattr(gs, "longAvgDelta", 0.0) - bgi), 0
            )

    # naive eventual BG
    if iob_array and getattr(iob_array[0], "iob", 0.0) > 0:
        naive_eventualBG = _round(bg - (iob_array[0].iob * sens), 0)
    else:
        # AAPS: тоже использует sens, а не min(sens, profile.sens)
        naive_eventualBG = _round(
            bg - ((iob_array[0].iob if iob_array else 0.0) * sens), 0
        )

    eventualBG = naive_eventualBG + deviation

    # threshold (LGS)
    threshold = min_bg - 0.5 * (min_bg - 40)
    if getattr(profile, "lgsThreshold", None) is not None:
        lgsThreshold = getattr(profile, "lgsThreshold")
        if lgsThreshold > threshold:
            console_err.append(
                f"Threshold set from {convert_bg(threshold)} to {convert_bg(float(lgsThreshold))}; "
            )
            threshold = float(lgsThreshold)

    # initialize prediction arrays with current bg
    COBpredBGs: List[float] = [bg]
    aCOBpredBGs: List[float] = [bg]
    IOBpredBGs: List[float] = [bg]
    UAMpredBGs: List[float] = [bg]
    ZTpredBGs: List[float] = [bg]

    enableUAM = getattr(profile, "enableUAM", False)

    ci = _round(
        min(getattr(gs, "delta", 0.0), getattr(gs, "shortAvgDelta", 0.0)) - bgi, 1
    )
    uci = ci

    carb_ratio = getattr(profile, "carb_ratio", None) or 1.0
    csf = sens / carb_ratio if carb_ratio != 0 else sens
    console_err.append(
        f"profile.sens: {getattr(profile, 'sens', None)}, sens: {sens}, CSF: {csf}"
    )

    maxCarbAbsorptionRate = 30
    maxCI = _round(maxCarbAbsorptionRate * csf * 5 / 60, 1)
    if ci > maxCI:
        console_err.append(f"Limiting carb impact from {ci} to {maxCI} mg/dL/5m")
        ci = maxCI

    remainingCATimeMin = 3.0
    remainingCATimeMin = remainingCATimeMin / sensitivityRatio
    assumedCarbAbsorptionRate = 20
    remainingCATime = remainingCATimeMin

    if getattr(meal_data, "carbs", 0.0) != 0.0:
        remainingCATimeMin = max(
            remainingCATimeMin,
            getattr(meal_data, "mealCOB", 0.0) / assumedCarbAbsorptionRate,
        )
        lastCarbAge = _round(
            (system_time - getattr(meal_data, "lastCarbTime", 0)) / 60000.0, 0
        )
        fractionCOBAbsorbed = (
            getattr(meal_data, "carbs", 0.0) - getattr(meal_data, "mealCOB", 0.0)
        ) / getattr(meal_data, "carbs", 1.0)
        remainingCATime = remainingCATimeMin + 1.5 * lastCarbAge / 60.0
        remainingCATime = _round(remainingCATime, 1)
        console_err.append(
            f"Last carbs {lastCarbAge} minutes ago; remainingCATime:{remainingCATime} hours;{_round(fractionCOBAbsorbed*100)}% carbs absorbed"
        )

    totalCI = max(0.0, ci / 5 * 60 * remainingCATime / 2)
    totalCA = totalCI / csf if csf != 0 else 0.0
    remainingCarbsCap = min(90, getattr(profile, "remainingCarbsCap", 90))
    remainingCarbs = max(0.0, getattr(meal_data, "mealCOB", 0.0) - totalCA)
    remainingCarbs = min(float(remainingCarbsCap), remainingCarbs)
    if remainingCATime <= 0:
        remainingCIpeak = 0.0
    else:
        remainingCIpeak = remainingCarbs * csf * 5.0 / 60.0 / (remainingCATime / 2.0)

    slopeFromMaxDeviation = _round(getattr(meal_data, "slopeFromMaxDeviation", 0.0), 2)
    slopeFromMinDeviation = _round(getattr(meal_data, "slopeFromMinDeviation", 0.0), 2)
    slopeFromDeviations = min(slopeFromMaxDeviation, -slopeFromMinDeviation / 3.0)

    aci = 10
    if ci == 0.0:
        cid = 0.0
    else:
        cid = min(
            remainingCATime * 60 / 5 / 2,
            max(0.0, getattr(meal_data, "mealCOB", 0.0) * csf / ci),
        )
    acid = max(0.0, getattr(meal_data, "mealCOB", 0.0) * csf / aci)
    console_err.append(
        f"Carb Impact: {ci} mg/dL per 5m; CI Duration: {_round(cid*5/60*2,1)} hours; remaining CI (~2h peak): {_round(remainingCIpeak,1)} mg/dL per 5m"
    )

    # initialize minima/maxima with inf/-inf
    minIOBPredBG = float("inf")
    minCOBPredBG = float("inf")
    minUAMPredBG = float("inf")
    minCOBGuardBG = float("inf")
    minUAMGuardBG = float("inf")
    minIOBGuardBG = float("inf")
    minZTGuardBG = float("inf")

    minPredBG = 0.0
    avgPredBG = 0.0
    IOBpredBG = eventualBG
    maxIOBPredBG = bg
    maxCOBPredBG = bg

    remainingCItotal = 0.0
    remainingCIs: List[int] = []
    predCIs: List[int] = []
    UAMpredBG_val: Optional[float] = None
    COBpredBG_val: Optional[float] = None
    aCOBpredBG_val: Optional[float] = None

    # main prediction loop
    for iobTick in iob_array:
        try:
            activity = float(getattr(iobTick, "activity", 0.0) or 0.0)
        except Exception:
            activity = 0.0
        try:
            activity_zt = float(
                getattr(getattr(iobTick, "iobWithZeroTemp", iobTick), "activity", 0.0)
                or 0.0
            )
        except Exception:
            activity_zt = 0.0

        predBGI = _round(-activity * sens * 5.0, 2)
        # AutoISF only: use sens for all pred types
        IOBpredBGI = _round(-activity * sens * 5.0, 2)
        predZTBGI = _round(-activity_zt * sens * 5.0, 2)
        predUAMBGI = _round(-activity * sens * 5.0, 2)

        predDev = ci * (1 - len(COBpredBGs) / max(cid * 2, 1.0)) if cid > 0 else 0.0

        IOBpredBG = IOBpredBGs[-1] + IOBpredBGI + predDev
        ZTpredBG = ZTpredBGs[-1] + predZTBGI

        predCI = (
            max(0.0, max(0.0, ci) * (1 - len(COBpredBGs) / max(cid * 2, 1.0)))
            if cid > 0
            else 0.0
        )
        predACI = (
            max(0.0, max(0, aci) * (1 - len(COBpredBGs) / max(acid * 2, 1.0)))
            if acid > 0
            else 0.0
        )

        intervals = min(
            float(len(COBpredBGs)), max(0.0, (remainingCATime * 12) - len(COBpredBGs))
        )
        remainingCI = (
            (intervals / (remainingCATime / 2 * 12) * remainingCIpeak)
            if remainingCATime > 0
            else 0.0
        )

        remainingCItotal += predCI + remainingCI
        remainingCIs.append(_round(remainingCI))
        predCIs.append(_round(predCI))

        COBpredBG_val = (
            COBpredBGs[-1] + predBGI + min(0.0, predDev) + predCI + remainingCI
        )
        aCOBpredBG_val = aCOBpredBGs[-1] + predBGI + min(0.0, predDev) + predACI

        predUCIslope = max(0.0, uci + (len(UAMpredBGs) * slopeFromDeviations))
        predUCImax = max(0.0, uci * (1 - len(UAMpredBGs) / max(3.0 * 60 / 5, 1.0)))
        predUCI = min(predUCIslope, predUCImax)
        if predUCI > 0:
            _round((len(UAMpredBGs) + 1) * 5 / 60.0, 1)

        UAMpredBG_val = UAMpredBGs[-1] + predUAMBGI + min(0.0, predDev) + predUCI

        # временная защита от абсурдных предсказаний при отладке
        def _clamp_pred(x):
            try:
                xv = float(x)
            except Exception:
                return 39.0
            if math.isnan(xv):
                return 39.0
            return max(-1000.0, min(2000.0, xv))

        COBpredBG_val = _clamp_pred(COBpredBG_val)
        UAMpredBG_val = _clamp_pred(UAMpredBG_val)

        if len(IOBpredBGs) < 48:
            IOBpredBGs.append(IOBpredBG)
        if len(COBpredBGs) < 48:
            COBpredBGs.append(COBpredBG_val)
        if len(aCOBpredBGs) < 48:
            aCOBpredBGs.append(aCOBpredBG_val)
        if len(UAMpredBGs) < 48:
            UAMpredBGs.append(UAMpredBG_val)
        if len(ZTpredBGs) < 48:
            ZTpredBGs.append(ZTpredBG)

        if COBpredBG_val < minCOBGuardBG:
            minCOBGuardBG = float(_round(COBpredBG_val, 0))
        if UAMpredBG_val < minUAMGuardBG:
            minUAMGuardBG = float(_round(UAMpredBG_val, 0))
        if IOBpredBG < minIOBGuardBG:
            minIOBGuardBG = IOBpredBG
        if ZTpredBG < minZTGuardBG:
            minZTGuardBG = _round(ZTpredBG, 0)

        insulinPeakTime = 90
        insulinPeak5m = (insulinPeakTime / 60.0) * 12.0

        if len(IOBpredBGs) > insulinPeak5m and IOBpredBG < minIOBPredBG:
            minIOBPredBG = _round(IOBpredBG, 0)
        if IOBpredBG > maxIOBPredBG:
            maxIOBPredBG = IOBpredBG

        if (
            (cid != 0.0 or remainingCIpeak > 0)
            and len(COBpredBGs) > insulinPeak5m
            and COBpredBG_val < minCOBPredBG
        ):
            minCOBPredBG = _round(COBpredBG_val, 0)
        if (cid != 0.0 or remainingCIpeak > 0) and COBpredBG_val > maxIOBPredBG:
            maxCOBPredBG = COBpredBG_val
        if enableUAM and len(UAMpredBGs) > 12 and UAMpredBG_val < minUAMPredBG:
            minUAMPredBG = _round(UAMpredBG_val, 0)

    # Если RT прислал UAM предсказания — используем их вместо вычисленного массива (гарантирует точное совпадение с AAPS)
    if rt_uam_override is not None:
        try:
            rt_list = [float(x) for x in rt_uam_override]
        except Exception:
            rt_list = list(rt_uam_override)
        # Если RT‑массив начинается не с текущего bg, добавим текущий bg в начало
        if len(rt_list) > 0 and float(rt_list[0]) != float(bg):
            UAMpredBGs = [bg] + rt_list
        else:
            UAMpredBGs = rt_list

    # finalize arrays and clamp values
    res = PredictionsResult()

    IOBpredBGs = [_round(min(401.0, max(39.0, x)), 0) for x in IOBpredBGs]
    for i in range(len(IOBpredBGs) - 1, 12, -1):
        if IOBpredBGs[i - 1] != IOBpredBGs[i]:
            break
        else:
            IOBpredBGs.pop()
    res.pred_iob = [int(x) for x in IOBpredBGs]
    float(_round(IOBpredBGs[-1], 0))

    ZTpredBGs = [_round(min(401.0, max(39.0, x)), 0) for x in ZTpredBGs]
    for i in range(len(ZTpredBGs) - 1, 6, -1):
        if ZTpredBGs[i - 1] >= ZTpredBGs[i] or ZTpredBGs[i] <= target_bg:
            break
        else:
            ZTpredBGs.pop()
    res.pred_zt = [int(x) for x in ZTpredBGs]

    if getattr(meal_data, "mealCOB", 0.0) > 0:
        aCOBpredBGs = [_round(min(401.0, max(39.0, x)), 0) for x in aCOBpredBGs]
        for i in range(len(aCOBpredBGs) - 1, 12, -1):
            if aCOBpredBGs[i - 1] != aCOBpredBGs[i]:
                break
            else:
                aCOBpredBGs.pop()

    if getattr(meal_data, "mealCOB", 0.0) > 0 and (ci > 0 or remainingCIpeak > 0):
        COBpredBGs = [_round(min(401.0, max(39.0, x)), 0) for x in COBpredBGs]
        for i in range(len(COBpredBGs) - 1, 12, -1):
            if COBpredBGs[i - 1] != COBpredBGs[i]:
                break
            else:
                COBpredBGs.pop()
        res.pred_cob = [int(x) for x in COBpredBGs]
        COBpredBGs[-1]
        eventualBG = max(eventualBG, _round(COBpredBGs[-1], 0))

    if ci > 0 or remainingCIpeak > 0:
        if enableUAM:
            UAMpredBGs = [_round(min(401.0, max(39.0, x)), 0) for x in UAMpredBGs]
            for i in range(len(UAMpredBGs) - 1, 12, -1):
                if UAMpredBGs[i - 1] != UAMpredBGs[i]:
                    break
                else:
                    UAMpredBGs.pop()
            res.pred_uam = [int(x) for x in UAMpredBGs]
            UAMpredBGs[-1]
            eventualBG = max(eventualBG, _round(UAMpredBGs[-1], 0))
    else:
        # Если RT предоставил UAM, но ci==0, всё равно выставим pred_uam, чтобы совпадать с AAPS
        if rt_uam_override is not None:
            UAMpredBGs = [_round(min(401.0, max(39.0, x)), 0) for x in UAMpredBGs]
            for i in range(len(UAMpredBGs) - 1, 12, -1):
                if UAMpredBGs[i - 1] != UAMpredBGs[i]:
                    break
                else:
                    UAMpredBGs.pop()
            res.pred_uam = [int(x) for x in UAMpredBGs]
            UAMpredBGs[-1]
            eventualBG = max(eventualBG, _round(UAMpredBGs[-1], 0))

    res.eventual_bg = eventualBG

    # fallback for minima
    if minIOBPredBG == float("inf"):
        minIOBPredBG = eventualBG
    if minCOBPredBG == float("inf"):
        minCOBPredBG = eventualBG
    if minUAMPredBG == float("inf"):
        minUAMPredBG = eventualBG

    minIOBPredBG = max(39.0, minIOBPredBG)
    minCOBPredBG = max(39.0, minCOBPredBG)
    minUAMPredBG = max(39.0, minUAMPredBG)
    minPredBG = _round(minIOBPredBG, 0)

    min(minPredBG, bg)

    fractionCarbsLeft = (
        getattr(meal_data, "mealCOB", 0.0) / getattr(meal_data, "carbs", 1.0)
        if getattr(meal_data, "carbs", 0.0) != 0
        else 0.0
    )

    if minUAMPredBG != float("inf") and minCOBPredBG != float("inf"):
        avgPredBG = _round(
            (1 - fractionCarbsLeft) * (UAMpredBG_val or IOBpredBG)
            + fractionCarbsLeft * (COBpredBG_val or IOBpredBG),
            0,
        )
    elif minCOBPredBG != float("inf"):
        avgPredBG = _round((IOBpredBG + (COBpredBG_val or IOBpredBG)) / 2.0, 0)
    elif minUAMPredBG != float("inf"):
        avgPredBG = _round((IOBpredBG + (UAMpredBG_val or IOBpredBG)) / 2.0, 0)
    else:
        avgPredBG = _round(IOBpredBG, 0)

    if minZTGuardBG > avgPredBG:
        avgPredBG = minZTGuardBG

    if cid > 0.0 or remainingCIpeak > 0:
        if enableUAM:
            minGuardBG = (
                fractionCarbsLeft * minCOBGuardBG
                + (1 - fractionCarbsLeft) * minUAMGuardBG
            )
        else:
            minGuardBG = minCOBGuardBG
    elif enableUAM:
        minGuardBG = minUAMGuardBG
    else:
        minGuardBG = minIOBGuardBG

    minGuardBG = _round(minGuardBG, 0)
    res.min_guard_bg = minGuardBG

    # compute minPredBG final blending
    minZTUAMPredBG = minUAMPredBG
    if minZTGuardBG < threshold:
        minZTUAMPredBG = (minUAMPredBG + minZTGuardBG) / 2.0
    elif minZTGuardBG < target_bg:
        blendPct = (
            (minZTGuardBG - threshold) / (target_bg - threshold)
            if (target_bg - threshold) != 0
            else 0.0
        )
        blendedMinZTGuardBG = minUAMPredBG * blendPct + minZTGuardBG * (1 - blendPct)
        minZTUAMPredBG = (minUAMPredBG + blendedMinZTGuardBG) / 2.0
    elif minZTGuardBG > minUAMPredBG:
        minZTUAMPredBG = (minUAMPredBG + minZTGuardBG) / 2.0

    minZTUAMPredBG = _round(minZTUAMPredBG, 0)

    if getattr(meal_data, "carbs", 0.0) != 0.0:
        if not enableUAM and minCOBPredBG != float("inf"):
            minPredBG = _round(max(minIOBPredBG, minCOBPredBG), 0)
        elif minCOBPredBG != float("inf"):
            blendedMinPredBG = (
                fractionCarbsLeft * minCOBPredBG
                + (1 - fractionCarbsLeft) * minZTUAMPredBG
            )
            minPredBG = _round(
                max(minIOBPredBG, max(minCOBPredBG, blendedMinPredBG)), 0
            )
        elif enableUAM:
            minPredBG = minZTUAMPredBG
        else:
            minPredBG = minGuardBG
    elif enableUAM:
        minPredBG = _round(max(minIOBPredBG, minZTUAMPredBG), 0)

    minPredBG = min(minPredBG, avgPredBG)

    if maxCOBPredBG > bg:
        minPredBG = min(minPredBG, maxCOBPredBG)

    res.min_pred_bg = minPredBG

    return res
