# aaps_emulator/core/autoisf_algorithm.py
"""
AutoISF algorithm utilities.

This file provides a defensive implementation of determine_basal_autoisf that:
 - accepts optional rt (runtime) predictions and extracts eventualBG from them when available
 - safely handles missing bg/delta values
 - uses autosens ratio and sensitivityRatio from rt when present
 - converts mg/dL -> mmol/L when appropriate (threshold-based)
 - computes insulinReq and maps it to rate with safeguards (duration, SMB scaling, caps)
 - returns AutoIsfResult(eventualBG, insulinReq, rate, duration)
"""

from dataclasses import dataclass
from typing import Optional, Any

# If your project has compute_autosens_ratio in core.autosens, keep this import.
# from core.autosens import compute_autosens_ratio


@dataclass
class AutoIsfResult:
    eventualBG: Optional[float]
    insulinReq: Optional[float]
    rate: float
    duration: int


def _extract_predicted_eventual_from_rt(rt_obj: Any) -> Optional[float]:
    """
    Try to extract predicted eventualBG from rt object (dict or string).
    Returns eventualBG in mmol/L or None.

    Handles:
      - dict with keys 'eventualBG', 'eventual_bg', 'predBGs', 'predictions'
      - string logs containing 'eventualBG=NNN'

    If value looks like mg/dL (>30), convert to mmol/L by dividing by 18.
    """
    if not rt_obj:
        return None

    # dict-like rt
    if isinstance(rt_obj, dict):
        ev = rt_obj.get("eventualBG") or rt_obj.get("eventual_bg") or rt_obj.get("eventual")
        if ev is not None:
            try:
                evf = float(ev)
                # threshold lowered to 30 to catch values like 39 mg/dL
                if evf > 30:
                    return evf / 18.0
                return evf
            except Exception:
                pass

        preds = rt_obj.get("predBGs") or rt_obj.get("predictions") or rt_obj.get("preds")
        if preds and isinstance(preds, (list, tuple)) and len(preds) > 0:
            try:
                last = float(preds[-1])
                if last > 30:
                    return last / 18.0
                return last
            except Exception:
                pass

        return None

    # string-like rt (parse eventualBG=NNN)
    try:
        s = str(rt_obj)
        marker = "eventualBG="
        if marker in s:
            part = s.split(marker, 1)[1]
            num = ""
            for ch in part:
                if (ch.isdigit() or ch in ".-"):
                    num += ch
                else:
                    break
            if num:
                val = float(num)
                if val > 30:
                    return val / 18.0
                return val
    except Exception:
        pass

    return None


def determine_basal_autoisf(
    glucose_status,
    currenttemp,
    iob_data_array,
    profile,
    autosens_data,
    meal_data,
    rt=None,   # optional: pass rt dict/string if available
    microBolusAllowed=False,
    currentTime=0,
    flatBGsDetected=False,
    autoIsfMode=True,
    loop_wanted_smb="none",
    profile_percentage=100,
    smb_ratio=0.5,
    smb_max_range_extension=1.0,
    iob_threshold_percent=100,
    auto_isf_consoleError=None,
    auto_isf_consoleLog=None
):
    """
    Defensive AutoISF calculation.

    - Uses rt predictions when available (rt may be dict or string).
    - Falls back to bg + delta*30 projection when no predictions.
    - Uses autosens_data.ratio or sensitivityRatio from rt when present.
    - Returns AutoIsfResult(eventualBG, insulinReq, rate, duration).
    """
    if auto_isf_consoleError is None:
        auto_isf_consoleError = []
    if auto_isf_consoleLog is None:
        auto_isf_consoleLog = []

    res = AutoIsfResult(eventualBG=None, insulinReq=None, rate=0.0, duration=30)

    if glucose_status is None or profile is None:
        auto_isf_consoleError.append("Missing glucose_status or profile")
        return res

    try:
        # ensure bg and delta are defined early and safely
        try:
            bg = getattr(glucose_status, "glucose", None)
        except Exception:
            bg = None
        try:
            delta = getattr(glucose_status, "delta", 0.0)
        except Exception:
            delta = 0.0

        # 1) Try to get predicted eventualBG from rt/predictions if available
        eventualBG = None
        rt_obj = rt
        if rt_obj:
            ev_from_rt = _extract_predicted_eventual_from_rt(rt_obj)
            if ev_from_rt is not None:
                eventualBG = ev_from_rt
                auto_isf_consoleLog.append(f"Using predicted eventualBG from rt: {eventualBG:.3f} mmol/L")

        # 2) fallback to simple delta projection if no predictions
        if eventualBG is None:
            # convert bg units if needed (mg/dL -> mmol/L)
            if bg is not None and bg > 50:
                bg = bg / 18.0
                auto_isf_consoleLog.append(f"Converted BG from mg/dL to mmol/L: {bg:.3f}")

            try:
                eventualBG = bg + (delta * 30.0)
            except Exception:
                eventualBG = None

            if eventualBG is None or eventualBG <= 0:
                auto_isf_consoleLog.append(f"Projected eventualBG invalid ({eventualBG}), falling back to current BG {bg}")
                eventualBG = bg

        # compute autosens ratio using provided autosens_data if present
        autosens_ratio = 1.0
        if autosens_data is not None:
            try:
                r = getattr(autosens_data, "ratio", None)
                if r is not None and r != 1.0:
                    autosens_ratio = float(r)
            except Exception:
                autosens_ratio = 1.0

        # prefer sensitivityRatio from rt if present
        try:
            sens_ratio_rt = None
            if rt_obj and isinstance(rt_obj, dict):
                sens_ratio_rt = rt_obj.get("sensitivityRatio") or rt_obj.get("sensitivity_ratio") or rt_obj.get("sensitivityRatioValue")
                if sens_ratio_rt is not None:
                    sens_ratio_rt = float(sens_ratio_rt)
            if sens_ratio_rt:
                autosens_ratio = float(sens_ratio_rt)
                auto_isf_consoleLog.append(f"Using sensitivityRatio from rt: {autosens_ratio:.3f}")
        except Exception:
            pass

        # effective sensitivity (rounded to reduce floating noise)
        prof_sens = getattr(profile, "variable_sens", None) or getattr(profile, "sens", None)
        if prof_sens is None or prof_sens == 0:
            prof_sens = 6.0
        prof_sens = round(float(prof_sens), 3)
        effective_sens = round(prof_sens * autosens_ratio, 4)
        if effective_sens == 0:
            effective_sens = prof_sens or 6.0

        # insulin requirement (U)
        target_bg = getattr(profile, "target_bg", None) or 6.4
        insulinReq = None
        try:
            insulinReq = (eventualBG - target_bg) / effective_sens
        except Exception:
            insulinReq = None

        # duration: prefer rt.duration, else predBGs length*5, else currenttemp, else default
        duration = 30
        try:
            if rt_obj and isinstance(rt_obj, dict):
                rt_dur = rt_obj.get("duration") or rt_obj.get("dur")
                if rt_dur is not None:
                    rd = int(float(rt_dur))
                    # if rt_dur looks like seconds convert to minutes
                    if rd > 300:
                        rd = max(5, rd // 60)
                    duration = max(5, rd)
                    auto_isf_consoleLog.append(f"Using duration from rt: {duration} minutes")
                else:
                    preds = rt_obj.get("predBGs") or rt_obj.get("predictions")
                    if preds and isinstance(preds, (list, tuple)):
                        duration = max(duration, len(preds) * 5)
        except Exception:
            pass

        try:
            if currenttemp is not None:
                dur = int(getattr(currenttemp, "duration", 0) or 0)
                if dur > 0:
                    duration = max(duration, dur)
        except Exception:
            pass

        if loop_wanted_smb and loop_wanted_smb != "none":
            duration = max(duration, 60)

        # compute raw rate (U/h) with safeguards
        rate = 0.0
        try:
            if insulinReq is not None:
                raw_rate = insulinReq * (60.0 / max(1, duration))

                # cap by profile.max_basal if present
                max_basal = getattr(profile, "max_basal", None)
                if max_basal is not None:
                    raw_rate = min(raw_rate, float(max_basal))

                # limit abrupt increases relative to current basal (tunable)
                current_basal = getattr(profile, "current_basal", 0.0) or 0.0
                max_delta_rate = 2.5  # U/h max allowed increase in one decision (tuneable)
                allowed_max = current_basal + max_delta_rate
                raw_rate = min(raw_rate, allowed_max)

                # SMB scaling: apply only for very small insulinReq to avoid underdelivery
                smb_threshold = 0.5  # U threshold below which SMB scaling is applied
                if abs(insulinReq) < smb_threshold and getattr(profile, "enableSMB_always", False):
                    smb_ratio_local = getattr(profile, "smb_delivery_ratio", smb_ratio or 0.5)
                    raw_rate = raw_rate * float(smb_ratio_local)

                rate = max(0.0, raw_rate)
        except Exception:
            rate = 0.0

        # fill result
        res.eventualBG = eventualBG
        res.insulinReq = insulinReq
        res.rate = rate
        res.duration = duration

        # safe string formatting for logs
        bg_str = f"{bg:.2f}" if (bg is not None) else "None"
        ev_str = f"{eventualBG:.2f}" if (eventualBG is not None) else "None"
        ins_str = f"{insulinReq:.3f}" if (insulinReq is not None) else "None"

        auto_isf_consoleLog.append(
            f"AutoISF calc: bg={bg_str}, delta={delta:.3f}, eventualBG={ev_str}, "
            f"prof_sens={prof_sens:.3f}, autosens_ratio={autosens_ratio:.3f}, effective_sens={effective_sens:.3f}, "
            f"insulinReq={ins_str}, duration={duration}, rate={rate:.3f}"
        )

        return res

    except Exception as e:
        auto_isf_consoleError.append(f"Exception in determine_basal_autoisf: {e}")
        return res
