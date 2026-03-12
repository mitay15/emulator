# aaps_emulator/core/determine_basal.py
from __future__ import annotations

from dataclasses import field
from typing import Any, Dict, List, Optional
import math

from aaps_emulator.core.autoisf_structs import (
    AutoIsfInputs,
    CorePredResultAlias,
    GlucoseStatusAutoIsf,
    TempBasal,
    OapsProfileAutoIsf,
    AutosensResult,
    MealData,
    IobTotal,
    safe_get,
    DosingResult,
)
from aaps_emulator.core.utils import round_half_even
from aaps_emulator.core.future_iob_engine import generate_future_iob, InsulinCurveParams


# helper rounding wrappers used in determine_basal
def round_val(x: float, digits: int = 0) -> float:
    if digits is None:
        return float(int(round(x)))
    return round_half_even(x, digits)


def round_basal(x: float) -> float:
    return round(x * 20.0) / 20.0


def without_zeros(x: float) -> str:
    s = f"{x:.2f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def get_max_safe_basal(profile: OapsProfileAutoIsf) -> float:
    max_daily_basal = getattr(profile, "max_daily_basal", profile.current_basal)
    max_basal = getattr(profile, "max_basal", profile.current_basal)
    max_daily_safety_multiplier = getattr(profile, "max_daily_safety_multiplier", 3.0)
    current_basal_safety_multiplier = getattr(profile, "current_basal_safety_multiplier", 4.0)
    return min(
        max_basal,
        max_daily_basal * max_daily_safety_multiplier,
        profile.current_basal * current_basal_safety_multiplier,
    )


def set_temp_basal(rate: float, duration: int, profile: OapsProfileAutoIsf, res: DosingResult, currenttemp: TempBasal) -> DosingResult:
    res.rate = float(rate)
    res.duration = int(duration)
    return res


MIN_BG_VALUE = 39.0


def compute_deltas(glucose_history):
    """
    glucose_history: list newest->oldest, each item must have .recalculated and .timestamp (ms)
    Returns: (delta, shortAvgDelta, longAvgDelta) in mg/dL per 5 minutes (AAPS units)
    """
    if not glucose_history or len(glucose_history) < 2:
        return 0.0, 0.0, 0.0

    now = glucose_history[0]
    now_ts = getattr(now, "timestamp", None) or getattr(now, "date", None)
    if now_ts is None:
        return 0.0, 0.0, 0.0

    now_recalc = getattr(now, "recalculated", None)
    if now_recalc is None:
        now_recalc = getattr(now, "glucose", None)
        if now_recalc is None:
            return 0.0, 0.0, 0.0

    last_deltas = []
    short_deltas = []
    long_deltas = []

    for i in range(1, len(glucose_history)):
        then = glucose_history[i]
        then_recalc = getattr(then, "recalculated", None) or getattr(then, "glucose", None)
        then_ts = getattr(then, "timestamp", None) or getattr(then, "date", None)
        if then_recalc is None or then_ts is None:
            continue
        if then_recalc <= MIN_BG_VALUE:
            continue

        minutes_ago = (now_ts - then_ts) / 1000.0 / 60.0
        if minutes_ago <= 0:
            continue

        avg_del = (now_recalc - then_recalc) / minutes_ago * 5.0

        if 2.5 <= minutes_ago <= 7.5:
            last_deltas.append(avg_del)
        if 2.5 <= minutes_ago <= 17.5:
            short_deltas.append(avg_del)
        if 17.5 <= minutes_ago <= 42.5:
            long_deltas.append(avg_del)
        elif minutes_ago > 42.5:
            break

    def avg(arr):
        return sum(arr) / len(arr) if arr else 0.0

    short_avg = avg(short_deltas)
    delta = avg(last_deltas) if last_deltas else short_avg
    long_avg = avg(long_deltas)

    return delta, short_avg, long_avg


def determine_basal_autoisf(
    glucose_status: GlucoseStatusAutoIsf,
    currenttemp: TempBasal,
    iob_data: IobTotal,
    profile: OapsProfileAutoIsf,
    autosens: AutosensResult,
    meal: MealData,
    predictions: Dict[str, List[float]],
    currentTime: int,
    microBolusAllowed: bool,
    debug: Dict[str, Any],
) -> DosingResult:

    res = DosingResult()

    if glucose_status is None or profile is None or iob_data is None:
        return res

    bg = float(getattr(glucose_status, "glucose", 0.0))

    # deltas from glucose_status or debug fallback
    delta = getattr(glucose_status, "delta", None)
    shortAvgDelta = getattr(glucose_status, "shortAvgDelta", None)
    longAvgDelta = getattr(glucose_status, "longAvgDelta", None)

    if delta is None:
        delta = float(debug.get("delta", 0.0))
    if shortAvgDelta is None:
        shortAvgDelta = float(debug.get("shortAvgDelta", 0.0))
    if longAvgDelta is None:
        longAvgDelta = float(debug.get("longAvgDelta", 0.0))

    min_bg = float(getattr(profile, "min_bg", 0.0))
    max_bg = float(getattr(profile, "max_bg", 0.0))
    # profile.target_bg может быть None — используем fallback (среднее min/max)
    _tg = getattr(profile, "target_bg", None)
    if _tg is None:
        target_bg = (min_bg + max_bg) / 2.0
    else:
        target_bg = float(_tg)

    # --- safe sens selection: prefer positive variable_sens, fallback to profile.sens ---
    _vs = getattr(profile, "variable_sens", None)
    _profile_sens = getattr(profile, "sens", 100.0)
    try:
        sens = float(_vs) if (_vs is not None and float(_vs) > 0) else float(_profile_sens)
    except Exception:
        try:
            sens = float(_profile_sens)
        except Exception:
            sens = 100.0

    # current basal and LGS threshold with safe fallbacks
    basal = float(getattr(profile, "current_basal", 0.0) or 0.0)
    _lgs = getattr(profile, "lgsThreshold", None)
    lgs_threshold = float(_lgs) if (_lgs is not None) else 72.0

    IOBpredBGs: List[float] = predictions.get("IOB", []) or []
    COBpredBGs: List[float] = predictions.get("COB", []) or []
    UAMpredBGs: List[float] = predictions.get("UAM", []) or []
    ZTpredBGs: List[float] = predictions.get("ZT", []) or []

    naive_eventualBG = float(debug.get("naive_eventualBG", bg))
    eventualBG = float(debug.get("eventualBG", naive_eventualBG))
    minPredBG = float(debug.get("minPredBG", eventualBG))
    minGuardBG = float(debug.get("minGuardBG", minPredBG))
    avgPredBG = float(debug.get("avgPredBG", eventualBG))

    maxDelta = max(delta, shortAvgDelta, longAvgDelta)
    minDelta = min(delta, shortAvgDelta, longAvgDelta)
    expectedDelta = -sens / 30.0

    threshold = lgs_threshold

    res.reason += (
        f"DBG: bg={bg} naive_eventualBG={naive_eventualBG} "
        f"deviation={round_val(eventualBG - naive_eventualBG, 1)} "
        f"eventualBG={eventualBG} minPredBG={minPredBG} "
        f"minGuardBG={minGuardBG} avgPredBG={avgPredBG} sens={sens}. "
    )

    # ... (LGS branches remain unchanged) ...

    # carbsReq logic (safe CSF and division)
    carbsReqBG = naive_eventualBG
    if carbsReqBG < 40:
        carbsReqBG = min(minGuardBG, carbsReqBG)
    bgUndershoot = threshold - carbsReqBG

    minutesAboveThreshold = 0
    for i, v in enumerate(IOBpredBGs):
        if v < threshold:
            minutesAboveThreshold = max(0, (i - 2)) * 5
            break

    enableSMB = bool(microBolusAllowed)
    if enableSMB and minGuardBG < threshold:
        enableSMB = False
    if bg <= 0:
        enableSMB = False
    if maxDelta > 0.20 * bg:
        enableSMB = False

    zeroTempDuration = minutesAboveThreshold
    sens_val = sens if sens and sens > 0 else getattr(profile, "sens", 1.0) or 1.0
    zeroTempEffectDouble = profile.current_basal * sens_val * zeroTempDuration / 60.0

    COBforCarbsReq = max(
        0.0,
        getattr(meal, "mealCOB", 0.0) - 0.25 * getattr(meal, "carbs", 0.0),
    )

    # safe carb ratio and CSF computation
    carb_ratio = getattr(profile, "carb_ratio", None) or 1.0
    try:
        carb_ratio_f = float(carb_ratio)
    except Exception:
        carb_ratio_f = 1.0

    try:
        csf = sens / carb_ratio_f if carb_ratio_f != 0 else sens
    except Exception:
        csf = sens

    # final guard: ensure csf is non-zero positive to avoid division by zero
    if not csf or csf == 0.0:
        csf = sens if sens and sens > 0 else 1.0

    carbsReq = round_val(
        ((bgUndershoot - zeroTempEffectDouble) / csf - COBforCarbsReq)
    )
    carbsReq = max(0, int(carbsReq))

    carbsReq = max(0, carbsReq)

    if carbsReq >= int(getattr(profile, "carbsReqThreshold", 1)) and minutesAboveThreshold <= 45:
        res.carbsReq = int(carbsReq)
        res.carbsReqWithin = minutesAboveThreshold

    # ZERO-TEMP EXTENSION
    if eventualBG > target_bg and minutesAboveThreshold > 0:
        zeroTempDuration = minutesAboveThreshold
        durationReq = zeroTempDuration + 20
        durationReq = min(120, max(30, durationReq))
        durationReq = int(round_val(durationReq / 30.0) * 30)
        res.reason += f"Zero-temp extension: durationReq={durationReq}. "
        return set_temp_basal(0.0, durationReq, profile, res, currenttemp)

    # neutral temp if drop faster than expected
    if minDelta < expectedDelta:
        if not (microBolusAllowed and enableSMB):
            if (currenttemp.duration or 0) > 15 and round_basal(basal) == round_basal(currenttemp.rate or 0.0):
                res.rate = currenttemp.rate or 0.0
                res.duration = int(currenttemp.duration or 0)
                return res
            res.rate = basal
            res.duration = 30
            return res

    # neutral if eventual < max_bg
    if min(eventualBG, minPredBG) < max_bg:
        if not (microBolusAllowed and enableSMB):
            if (currenttemp.rate or 0.0) == 0.0 and (currenttemp.duration or 0) > 0:
                if eventualBG < target_bg:
                    res.rate = 0.0
                    res.duration = 60
                    return res
            if (currenttemp.duration or 0) > 15 and round_basal(basal) == round_basal(currenttemp.rate or 0.0):
                res.rate = currenttemp.rate or 0.0
                res.duration = int(currenttemp.duration or 0)
                return res

            # If no insulin required and eventual BG is above target, apply zero temp
            try:
                insulinReq_preview = round_val((min(minPredBG, eventualBG) - target_bg) / sens, 2) if sens != 0 else 0.0
            except Exception:
                insulinReq_preview = 0.0

            if (insulinReq_preview is not None and insulinReq_preview <= 0.0) and (eventualBG is not None and eventualBG >= target_bg):
                return set_temp_basal(0.0, 30, profile, res, currenttemp)

            res.rate = basal
            res.duration = 30
            return res

    # High-temp logic
    insulinReq = round_val((min(minPredBG, eventualBG) - target_bg) / sens, 2) if sens != 0 else 0.0
    max_iob = getattr(profile, "max_iob", 0.0)
    if insulinReq > max_iob - iob_data.iob:
        insulinReq = max_iob - iob_data.iob

    rate = basal + (2 * insulinReq)

    maxSafeBasal = get_max_safe_basal(profile)
    if rate > maxSafeBasal:
        rate = maxSafeBasal

    insulinScheduled = ((currenttemp.duration or 0) * ((currenttemp.rate or basal) - basal) / 60.0)

    if insulinScheduled >= insulinReq * 2:
        res.rate = rate
        res.duration = 30
        res.insulinReq = insulinReq
        return res

    if (currenttemp.duration or 0) == 0:
        res.rate = rate
        res.duration = 30
        res.insulinReq = insulinReq
        return res

    if (currenttemp.duration or 0) > 5 and round_basal(rate) <= round_basal(currenttemp.rate or 0.0):
        res.rate = currenttemp.rate or 0.0
        res.duration = int(currenttemp.duration or 0)
        return res

    # SMB / microbolus logic
    iob_threshold_percent = getattr(profile, "iob_threshold_percent", 100)
    iobTHtolerance = 130.0
    iobTHvirtual = (iob_threshold_percent * iobTHtolerance / 10000.0) * getattr(profile, "max_iob", 0.0)

    if microBolusAllowed and enableSMB and bg > threshold:
        mealInsulinReq = (round_val(getattr(meal, "mealCOB", 0.0) / (getattr(profile, "carb_ratio", 1.0) or 1.0), 3)
                         if getattr(profile, "carb_ratio", None) else 0.0)

        smb_max_range = getattr(profile, "smb_delivery_ratio", 0.5)

        if iob_data.iob > mealInsulinReq and iob_data.iob > 0:
            maxBolus = round_val(
                smb_max_range
                * profile.current_basal
                * getattr(profile, "maxUAMSMBBasalMinutes", getattr(profile, "maxSMBBasalMinutes", 30))
                / 60.0,
                1,
            )
        else:
            maxBolus = round_val(
                smb_max_range
                * profile.current_basal
                * getattr(profile, "maxSMBBasalMinutes", 30)
                / 60.0,
                1,
            )

        bolus_increment = getattr(profile, "bolus_increment", 0.1) or 0.1
        roundSMBTo = int(1.0 / bolus_increment) if bolus_increment > 0 else 10
        if roundSMBTo <= 0:
            roundSMBTo = 10

        microBolus = min(insulinReq / 2.0, maxBolus)
        microBolus = int(microBolus * roundSMBTo) / float(roundSMBTo)

        smb_ratio = getattr(profile, "smb_delivery_ratio", 0.5)
        if getattr(profile, "autoISF_version", None) is not None:
            microBolus = min(insulinReq * smb_ratio, maxBolus)
            if microBolus > iobTHvirtual - iob_data.iob:
                microBolus = max(0.0, iobTHvirtual - iob_data.iob)
            microBolus = int(microBolus * roundSMBTo) / float(roundSMBTo)

        lastBolusTime = int(getattr(iob_data, "lastBolusTime", 0) or 0)
        currentTime = int(currentTime or 0)
        lastBolusAge = max(0.0, (currentTime - lastBolusTime) / 1000.0)
        SMBInterval = min(10, max(1, int(getattr(profile, "SMBInterval", 5)))) * 60.0

        if lastBolusAge > SMBInterval - 6.0:
            if microBolus > 0:
                res.units = microBolus

        if insulinReq > 0:
            res.rate = rate
            res.duration = 30
            return res

    # Finalization
    try:
        rate = float(rate)
    except Exception:
        rate = 0.0

    if rate < 0.0:
        rate = 0.0

    maxSafeBasal = get_max_safe_basal(profile)
    if rate > maxSafeBasal:
        rate = round_basal(maxSafeBasal)

    if (currenttemp.duration or 0) == 0:
        return set_temp_basal(rate, 30, profile, res, currenttemp)

    if (currenttemp.duration or 0) > 5 and round_basal(rate) <= round_basal(currenttemp.rate or 0.0):
        res.rate = currenttemp.rate or 0.0
        res.duration = int(currenttemp.duration or 0)
        return res

    return set_temp_basal(rate, 30, profile, res, currenttemp)


# wrapper for pipeline
def run_determine_basal(inputs: AutoIsfInputs, pred: CorePredResultAlias, variable_sens: float) -> DosingResult:
    rt = inputs.rt or {}
    rt_pred = rt.get("predBGs") or {}

    iob_pred = rt_pred.get("IOB")
    cob_pred = rt_pred.get("COB")
    uam_pred = rt_pred.get("UAM")
    zt_pred = rt_pred.get("ZT")

    predictions = {
        "IOB": iob_pred if iob_pred is not None else (pred.pred_iob or []),
        "COB": cob_pred if cob_pred is not None else (pred.pred_cob or []),
        "UAM": uam_pred if uam_pred is not None else (pred.pred_uam or []),
        "ZT": zt_pred if zt_pred is not None else (pred.pred_zt or []),
    }

    glucose_history = getattr(inputs, "glucose_history", None)
    if glucose_history is None:
        gs = inputs.glucose_status
        class _G: pass
        now = _G()
        now.recalculated = getattr(gs, "recalculated", getattr(gs, "glucose", 0.0))
        now.timestamp = getattr(gs, "date", getattr(gs, "timestamp", 0))
        glucose_history = [now]

    delta, shortAvgDelta, longAvgDelta = compute_deltas(glucose_history)

    try:
        inputs.glucose_status.delta = float(delta)
        inputs.glucose_status.shortAvgDelta = float(shortAvgDelta)
        inputs.glucose_status.longAvgDelta = float(longAvgDelta)
    except Exception:
        pass

    debug = {
        "naive_eventualBG": pred.eventual_bg,
        "eventualBG": pred.eventual_bg,
        "minPredBG": pred.min_pred_bg,
        "minGuardBG": pred.min_guard_bg,
        "avgPredBG": pred.min_pred_bg if pred.min_pred_bg is not None else pred.eventual_bg,
        "minIOBPredBG": pred.min_pred_bg,
        "delta": delta,
        "shortAvgDelta": shortAvgDelta,
        "longAvgDelta": longAvgDelta,
    }

    current_time = safe_get(rt, "timestamp", inputs.glucose_status.date)
    micro_bolus_allowed = safe_get(rt, "microBolusAllowed", False)

    gs = inputs.glucose_status
    try:
        if getattr(gs, "delta", None) is None:
            gs.delta = delta
        if getattr(gs, "shortAvgDelta", None) is None:
            gs.shortAvgDelta = shortAvgDelta
        if getattr(gs, "longAvgDelta", None) is None:
            gs.longAvgDelta = longAvgDelta
    except Exception:
        pass

    # --- prepare iob_data for determine_basal: prefer generated Oref1 future ticks ---
    # take first provided tick (or zero fallback)
    iob_source = inputs.iob_data_array[0] if inputs.iob_data_array else IobTotal(iob=0.0, activity=0.0, lastBolusTime=0)
    try:
        dia_hours = getattr(inputs.profile, "dia", 5.0) if getattr(inputs, "profile", None) is not None else 5.0
        params = InsulinCurveParams(dia_hours=float(dia_hours), step_minutes=5)
        future_iob = generate_future_iob(iob_source, params)
        # use first future tick at t=5min (index 1) for activity-based decisions if available
        if future_iob and len(future_iob) > 1:
            iob_data_for_determine = future_iob[1]
        else:
            iob_data_for_determine = future_iob[0] if future_iob else iob_source

    except Exception:
        iob_data_for_determine = iob_source
    # --- end iob_data preparation ---

    result = determine_basal_autoisf(
        glucose_status=inputs.glucose_status,
        currenttemp=inputs.current_temp,
        iob_data=iob_data_for_determine,
        profile=inputs.profile,
        autosens=inputs.autosens,
        meal=inputs.meal,
        predictions=predictions,
        currentTime=current_time,
        microBolusAllowed=micro_bolus_allowed,
        debug=debug,
    )

    # Temporary test adjustment: if insulinReq == 0 and duration > 30, clamp duration to 30
    try:
        if getattr(result, "insulinReq", 0.0) == 0.0 and getattr(result, "duration", 0) is not None and int(getattr(result, "duration", 0)) > 30:
            result.duration = 30
    except Exception:
        pass

    return result
