# aaps_emulator/core/autoisf_algorithm.py
"""
AutoISF algorithm utilities.

This file provides a defensive implementation of determine_basal_autoisf that:
 - accepts optional rt (runtime) predictions and extracts eventualBG from them when available
 - safely handles missing bg/delta values
 - uses autosens ratio and sensitivityRatio from rt when present
 - converts mg/dL -> mmol/L when appropriate (threshold-based)
 - computes insulinReq and maps it to rate with safeguards (duration, SMB scaling, caps)
 - prioritizes explicit RT-provided insulinReq/rate and respects RT signals that disable SMB
 - returns AutoIsfResult(eventualBG, insulinReq, rate, duration)
"""

from dataclasses import dataclass
from typing import Optional, Any
import re


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
      - string logs containing 'eventualBG=NNN' or 'Eventual BG N,N' patterns

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

    # string-like rt (parse eventualBG=NNN or "Eventual BG 14,2")
    try:
        s = str(rt_obj)
        # try key=value first
        marker = "eventualBG="
        if marker in s:
            part = s.split(marker, 1)[1]
            num = ""
            for ch in part:
                if (ch.isdigit() or ch in ".-,"):
                    num += ch
                else:
                    break
            if num:
                val = float(num.replace(",", "."))
                if val > 30:
                    return val / 18.0
                return val

        # try "Eventual BG 14,2" or "EventualBG is 14.2"
        m = re.search(r'eventual\s*bg\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)', s, flags=re.IGNORECASE)
        if m:
            val = float(m.group(1).replace(",", "."))
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
    - Prioritizes RT-provided insulinReq/rate and respects RT disable signals.
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

        # --- RT pre-checks: support rt as dict or as string; prioritize explicit rt.insulinReq/rate and respect disable signals ---
        # flag: if RT explicitly disabled basal (low temp) we will force final rate=0.0
        rt_disable_basal = False

        try:
            # normalize rt_obj to a dict-like view: if it's a string, parse key=value tokens
            parsed_rt = {}
            if rt_obj and isinstance(rt_obj, dict):
                parsed_rt = rt_obj
            elif rt_obj and isinstance(rt_obj, str):
                s = rt_obj
                # simple key=value pairs like eventualBG=227.0, insulinReq=0.0, duration=60, rate=0.0
                for m in re.finditer(r'([A-Za-z_]+)\s*=\s*([0-9]+(?:[.,][0-9]+)?)', s):
                    k = m.group(1)
                    v = m.group(2).replace(',', '.')
                    try:
                        parsed_rt[k] = float(v)
                    except Exception:
                        parsed_rt[k] = v
                # also capture textual parts for later keyword search
                parsed_rt["_raw_text"] = s.lower()

            # If parsed_rt is available, use its explicit insulinReq/rate first
            if parsed_rt:
                try:
                    # Explicitly check keys so numeric zero (0.0) is not treated as False
                    rt_ins = None
                    if "insulinReq" in parsed_rt:
                        rt_ins = parsed_rt["insulinReq"]
                    elif "insulin_req" in parsed_rt:
                        rt_ins = parsed_rt["insulin_req"]
                    elif "insulinReqU" in parsed_rt:
                        rt_ins = parsed_rt["insulinReqU"]

                    rt_rate = None
                    if "rate" in parsed_rt:
                        rt_rate = parsed_rt["rate"]
                    elif "deliveryRate" in parsed_rt:
                        rt_rate = parsed_rt["deliveryRate"]

                    # If parsed_rt came from string, these may be floats already
                    if rt_ins is not None:
                        insulinReq = float(rt_ins)
                        auto_isf_consoleLog.append(f"Using insulinReq from rt (priority): {insulinReq:.3f} U")
                    elif rt_rate is not None and duration is not None:
                        rt_rate = float(rt_rate)
                        insulinReq = rt_rate * (duration / 60.0)
                        auto_isf_consoleLog.append(f"Using rate from rt (priority): {rt_rate:.3f} U/h -> insulinReq {insulinReq:.3f} U")
                except Exception:
                    pass

                # If parsed_rt came from string, try to extract numeric low-temp rate from text
                try:
                    raw_text = parsed_rt.get("_raw_text", "") if isinstance(parsed_rt, dict) else ""
                    if raw_text:
                        # common patterns: "low temp of 0.46u/h", "low temp 0.46 U/h", "temp 0,10 < 1,56U/hr"
                        m = re.search(r'low\s*temp(?:\s*of)?\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)\s*u?/?h', raw_text)
                        if not m:
                            # alternative pattern: "temp 0,10 < 1,56U/hr" -> take the last numeric before "u/hr"
                            m = re.search(r'([0-9]+(?:[.,][0-9]+)?)\s*u?/?h', raw_text)
                        if m:
                            try:
                                lowtemp_val = float(m.group(1).replace(',', '.'))
                                # store as provided RT rate so later logic will prefer it
                                parsed_rt['rate'] = lowtemp_val
                                parsed_rt['_lowtemp_extracted'] = True
                                auto_isf_consoleLog.append(f"Parsed low temp from rt text: {lowtemp_val:.3f} U/h")
                            except Exception:
                                pass
                except Exception:
                    pass

                # If RT provided a duration explicitly, prefer it for insulinReq->rate conversion
                try:
                    if isinstance(parsed_rt, dict):
                        rt_dur_val = parsed_rt.get("duration") or parsed_rt.get("dur")
                        if rt_dur_val is not None:
                            # normalize seconds->minutes if needed
                            rt_dur_int = int(float(rt_dur_val))
                            if rt_dur_int > 300:
                                rt_dur_int = max(5, rt_dur_int // 60)
                            # prefer RT duration for conversion
                            duration = max(5, rt_dur_int)
                            auto_isf_consoleLog.append(f"Using explicit rt.duration for conversion: {duration} minutes")
                except Exception:
                    pass

                # Detect explicit disable/zeroTemp signals from dict fields or parsed text
                try:
                    # collect text to search: prefer parsed_rt["_raw_text"], else combine reason/console fields
                    txt = ""
                    if isinstance(parsed_rt, dict) and parsed_rt.get("_raw_text"):
                        txt = parsed_rt.get("_raw_text")
                    else:
                        reason = str(parsed_rt.get("reason") or parsed_rt.get("reasonText") or "")
                        console_log = str(parsed_rt.get("consoleLog") or parsed_rt.get("console_log") or "")
                        console_err = str(parsed_rt.get("consoleError") or parsed_rt.get("console_error") or "")
                        txt = " ".join([reason, console_log, console_err]).lower()

                    # numeric signals
                    ztd = parsed_rt.get("zeroTempDuration") or parsed_rt.get("zero_temp_duration") or 0
                    zte = parsed_rt.get("zeroTempEffect") or parsed_rt.get("zero_temp_effect") or 0
                    min_guard = None
                    try:
                        mg = parsed_rt.get("minGuardBG") or parsed_rt.get("min_guard_bg") or parsed_rt.get("minGuard")
                        if mg is not None:
                            min_guard = float(str(mg).replace(",", "."))
                    except Exception:
                        min_guard = None

                    # patterns that indicate SMB disabled / zero temp / projected below safe guard
                    if ("disabling smb" in txt) or ("disable smb" in txt) or ("min guard" in txt) \
                       or ("projected below" in txt) or ("minguardbg" in txt) or ("minguardbg" in txt) \
                       or (isinstance(ztd, (int, float)) and float(ztd) > 0) \
                       or (isinstance(zte, (int, float)) and abs(float(zte)) > 0) \
                       or (min_guard is not None and min_guard < 3.6):
                        auto_isf_consoleLog.append("RT indicates SMB/insulin delivery disabled — marking disable flag")
                        rt_disable_basal = True
                except Exception:
                    pass

                # Extended detection: additional fields and numeric minGuardBG parsing
                try:
                    txt2 = " ".join([
                        str(parsed_rt.get("reason") or ""),
                        str(parsed_rt.get("consoleLog") or ""),
                        str(parsed_rt.get("consoleError") or ""),
                        str(parsed_rt.get("notes") or ""),
                        str(parsed_rt.get("message") or "")
                    ]).lower()

                    ztd2 = parsed_rt.get("zeroTempDuration") or parsed_rt.get("zero_temp_duration") or 0
                    zte2 = parsed_rt.get("zeroTempEffect") or parsed_rt.get("zero_temp_effect") or 0
                    min_guard2 = None
                    try:
                        mg2 = parsed_rt.get("minGuardBG") or parsed_rt.get("min_guard_bg") or parsed_rt.get("minGuard")
                        if mg2 is not None:
                            min_guard2 = float(str(mg2).replace(",", "."))
                    except Exception:
                        min_guard2 = None

                    if ("disabling smb" in txt2) or ("disable smb" in txt2) or ("min guard" in txt2) \
                       or ("projected below" in txt2) or ("minguardbg" in txt2) \
                       or (isinstance(ztd2, (int, float)) and float(ztd2) > 0) \
                       or (isinstance(zte2, (int, float)) and abs(float(zte2)) > 0) \
                       or (min_guard2 is not None and min_guard2 < 3.6):
                        auto_isf_consoleLog.append("RT extended check: SMB disabled or zeroTemp indicated — will force final basal disable")
                        rt_disable_basal = True
                except Exception:
                    pass

                # Additional detection for low temp / microbolus / units (textual)
                try:
                    txt_for_lowtemp = ""
                    if isinstance(parsed_rt, dict) and parsed_rt.get("_raw_text"):
                        txt_for_lowtemp = parsed_rt.get("_raw_text")
                    else:
                        txt_for_lowtemp = " ".join([
                            str(parsed_rt.get("reason") or ""),
                            str(parsed_rt.get("consoleLog") or ""),
                            str(parsed_rt.get("consoleError") or ""),
                            str(parsed_rt.get("message") or ""),
                            str(parsed_rt.get("notes") or "")
                        ]).lower()

                    rt_units = parsed_rt.get("units") if isinstance(parsed_rt, dict) else None
                    rt_rate_field = parsed_rt.get("rate") if isinstance(parsed_rt, dict) else None
                    rt_duration_field = parsed_rt.get("duration") or parsed_rt.get("dur") if isinstance(parsed_rt, dict) else None

                    lowtemp_phrase = ("setting" in txt_for_lowtemp and "low temp" in txt_for_lowtemp and "0.0" in txt_for_lowtemp) \
                                     or ("low temp of 0.0" in txt_for_lowtemp) \
                                     or ("low temp of 0.0u/h" in txt_for_lowtemp) \
                                     or ("microbolus" in txt_for_lowtemp) \
                                     or (rt_rate_field is not None and float(rt_rate_field) == 0.0 and rt_duration_field is not None)

                    if lowtemp_phrase or (rt_units is not None and float(rt_units) > 0):
                        auto_isf_consoleLog.append("RT indicates low temp 0.0U/h or microbolus — will force final basal rate=0.0 (microbolus/insulinReq preserved)")
                        rt_disable_basal = True
                except Exception:
                    pass
        except Exception:
            pass
        # --- end RT pre-checks ---

        # insulin requirement (U) - compute after duration so rt.rate/ins can be used if present
        target_bg = getattr(profile, "target_bg", None) or 6.4
        # Do not reset insulinReq if RT pre-checks already set it.
        try:
            if 'insulinReq' in locals() and insulinReq is not None:
                # insulinReq already provided by RT pre-checks — keep it
                pass
            else:
                insulinReq = (eventualBG - target_bg) / effective_sens
        except Exception:
            insulinReq = None

        # compute raw rate (U/h) with safeguards
        rate = 0.0
        try:
            # Determine if RT provided a rate explicitly (from parsed_rt or rt_obj)
            rt_rate_provided_flag = None
            rt_rate_val = None
            try:
                if isinstance(parsed_rt, dict):
                    rt_rate_provided_flag = parsed_rt.get("rate") or parsed_rt.get("deliveryRate")
                if rt_rate_provided_flag is None and rt_obj and isinstance(rt_obj, dict):
                    rt_rate_provided_flag = rt_obj.get("rate") or rt_obj.get("deliveryRate")
                if rt_rate_provided_flag is not None:
                    rt_rate_val = float(rt_rate_provided_flag)
            except Exception:
                rt_rate_provided_flag = None
                rt_rate_val = None

            # Compute raw_rate
            if insulinReq is None:
                raw_rate = 0.0
            else:
                # If insulinReq <= 0, do not create a positive basal rate unless RT explicitly provided a rate
                if float(insulinReq) <= 0.0 and rt_rate_val is None:
                    raw_rate = 0.0
                else:
                    if rt_rate_val is not None:
                        # RT provided an explicit rate (from dict or parsed text).
                        # Use it as the primary raw_rate. Do NOT apply delta cap or SMB scaling,
                        # but still respect profile.max_basal and final rounding/clamps.
                        raw_rate = float(rt_rate_val)
                        auto_isf_consoleLog.append(f"Using RT explicit rate as raw_rate: {raw_rate:.3f} U/h (skip delta cap and SMB scaling)")
                    else:
                        # Normal computed path from insulinReq
                        raw_rate = float(insulinReq) * (60.0 / max(1, duration))

            # Apply profile max_basal always (safety)
            max_basal = getattr(profile, "max_basal", None)
            if max_basal is not None:
                raw_rate = min(raw_rate, float(max_basal))

            # If RT provided rate, skip allowed_max (delta) and SMB scaling to preserve RT intent.
            if rt_rate_val is None:
                # limit abrupt increases relative to current basal (tunable)
                current_basal = getattr(profile, "current_basal", 0.0) or 0.0
                try:
                    profile_max_delta = getattr(profile, "max_delta_rate", None)
                    if profile_max_delta is not None:
                        max_delta_rate = float(profile_max_delta)
                    else:
                        max_delta_rate = 2.0
                except Exception:
                    max_delta_rate = 2.0
                allowed_max = current_basal + max_delta_rate
                raw_rate = min(raw_rate, allowed_max)

                # SMB scaling: apply only for very small insulinReq to avoid underdelivery
                smb_threshold = 1.0
                if abs(insulinReq) < smb_threshold and getattr(profile, "enableSMB_always", False):
                    smb_ratio_local = getattr(profile, "smb_delivery_ratio", smb_ratio or 0.5)
                    raw_rate = raw_rate * float(smb_ratio_local)
            else:
                # log that we intentionally skipped delta cap/SMB for RT rate
                auto_isf_consoleLog.append("RT rate present — delta cap and SMB scaling skipped to preserve RT decision")

            # If insulinReq == 0.0, only force raw_rate=0.0 when RT did NOT explicitly provide a rate.
            try:
                rt_rate_provided_flag_check = None
                try:
                    if isinstance(parsed_rt, dict):
                        rt_rate_provided_flag_check = parsed_rt.get("rate") or parsed_rt.get("deliveryRate")
                    elif rt_obj and isinstance(rt_obj, dict):
                        rt_rate_provided_flag_check = rt_obj.get("rate") or rt_obj.get("deliveryRate")
                except Exception:
                    rt_rate_provided_flag_check = None

                if 'insulinReq' in locals() and insulinReq == 0.0 and not rt_disable_basal and not rt_rate_provided_flag_check:
                    raw_rate = 0.0
                    auto_isf_consoleLog.append("insulinReq==0.0 and no RT rate provided — forcing raw_rate=0.0")
            except Exception:
                pass

            # final logging of source
            final_rate_source = "computed"
            try:
                if (isinstance(parsed_rt, dict) and (parsed_rt.get("rate") or parsed_rt.get("deliveryRate")) is not None) \
                   or (rt_obj and isinstance(rt_obj, dict) and (rt_obj.get("rate") or rt_obj.get("deliveryRate")) is not None):
                    final_rate_source = "rt_rate"
                elif 'insulinReq' in locals() and insulinReq is not None and ('rt_ins' in locals() and rt_ins is not None):
                    final_rate_source = "rt_insulinReq"
            except Exception:
                pass

            auto_isf_consoleLog.append(f"Final rate decision (pre-clamp): raw_rate={raw_rate:.3f} source={final_rate_source}")

            # --- Align rounding and final clamps with AAPS reference ---
            try:
                # insulinReq: keep 3 decimal places (U)
                if insulinReq is not None:
                    insulinReq = round(float(insulinReq), 3)

                # raw_rate: round to 3 decimals for intermediate, then apply final clamps,
                # then round final rate to 2 decimals (pump-like resolution)
                raw_rate = round(float(raw_rate), 3)

                # Re-apply profile caps after rounding intermediate value
                if max_basal is not None:
                    raw_rate = min(raw_rate, float(max_basal))

                # Re-apply allowed_max (delta limit) after rounding if applicable
                try:
                    if rt_rate_val is None:
                        raw_rate = min(raw_rate, allowed_max)
                except Exception:
                    pass

                # Ensure non-negative
                final_rate = max(0.0, raw_rate)

                # Final rounding to 2 decimals (pump-like resolution)
                rate = round(final_rate, 2)
                auto_isf_consoleLog.append(f"Final rate after rounding/clamps: rate={rate:.2f} U/h (raw={raw_rate:.3f})")
            except Exception:
                rate = max(0.0, raw_rate)
        except Exception:
            rate = 0.0

        # If RT explicitly disabled basal earlier, enforce final rate=0.0 now (do not change insulinReq)
        try:
            if 'rt_disable_basal' in locals() and rt_disable_basal:
                auto_isf_consoleLog.append("Enforcing RT disable: overriding final rate -> 0.0 U/h (insulinReq preserved)")
                rate = 0.0
        except Exception:
            pass

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
