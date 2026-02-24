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

import logging
import re
from dataclasses import dataclass
from typing import Any

from aaps_emulator.core.rt_parser import extract_lowtemp_rate, parse_rt_to_dict

logger = logging.getLogger(__name__)


@dataclass
class AutoIsfResult:
    eventualBG: float | None
    insulinReq: float | None
    rate: float
    duration: int


class TraceCollector:
    def __init__(self):
        self.steps: list[tuple[str, Any]] = []

    def add(self, name: str, value: Any) -> None:
        try:
            if hasattr(value, "__dict__"):
                value = value.__dict__
        except Exception as e:
            logger.debug(f"TraceCollector: suppressed exception: {e}")
        self.steps.append((name, value))

    def dump(self) -> list[tuple[str, Any]]:
        return self.steps


def trace(tc: TraceCollector | None, name: str, value: Any) -> None:
    if tc is not None:
        tc.add(name, value)


def _extract_predicted_eventual_from_rt(rt_obj: Any) -> float | None:
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
                logger.exception("autoisf_algorithm: suppressed exception")

        preds = rt_obj.get("predBGs") or rt_obj.get("predictions") or rt_obj.get("preds")
        if preds and isinstance(preds, (list, tuple)) and len(preds) > 0:
            try:
                last = float(preds[-1])
                if last > 30:
                    return last / 18.0
                return last
            except Exception:
                logger.exception("autoisf_algorithm: suppressed exception in preds parsing")

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
                if ch.isdigit() or ch in ".-,":
                    num += ch
                else:
                    break
            if num:
                val = float(num.replace(",", "."))
                if val > 30:
                    return val / 18.0
                return val

        # try "Eventual BG 14,2" or "EventualBG is 14.2"
        m = re.search(r"eventual\s*bg\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            val = float(m.group(1).replace(",", "."))
            if val > 30:
                return val / 18.0
            return val
    except Exception:
        logger.exception("autoisf_algorithm: suppressed exception in eventualBG projection")

    return None


def determine_basal_autoisf(
    glucose_status,
    currenttemp,
    iob_data_array,
    profile,
    autosens_data,
    meal_data,
    rt=None,  # optional: pass rt dict/string if available
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
    auto_isf_consoleLog=None,
    trace_mode: bool = False,
):
    """
    Defensive AutoISF calculation.

    - Uses rt predictions when available (rt may be dict or string).
    - Falls back to bg + delta*30 projection when no predictions.
    - Uses autosens_data.ratio or sensitivityRatio from rt when present.
    - Prioritizes RT-provided insulinReq/rate and respects RT disable signals.
    - Returns AutoIsfResult(eventualBG, insulinReq, rate, duration).
    """
    tc = TraceCollector() if trace_mode else None

    # ensure rt is normalized dict with snake_case keys
    try:
        from aaps_emulator.parsing.rt_parser import normalize_rt

        if rt is not None:
            # normalize strings and dicts to canonical snake_case/mmol values
            rt = normalize_rt(rt)
    except Exception as exc:
        # keep original rt but record the issue for diagnostics
        import logging

        logger = logging.getLogger(__name__)
        logger.debug("normalize_rt not applied: %s", exc)

    if auto_isf_consoleError is None:
        auto_isf_consoleError = []
    if auto_isf_consoleLog is None:
        auto_isf_consoleLog = []

    res = AutoIsfResult(eventualBG=None, insulinReq=None, rate=0.0, duration=30)

    trace(tc, "input.glucose_status", glucose_status)
    trace(tc, "input.currenttemp", currenttemp)
    trace(tc, "input.iob_data_array", iob_data_array)
    trace(tc, "input.profile", profile)
    trace(tc, "input.autosens_data", autosens_data)
    trace(tc, "input.meal_data", meal_data)
    trace(tc, "input.rt", rt)

    if glucose_status is None or profile is None:
        auto_isf_consoleError.append("Missing glucose_status or profile")
        if trace_mode and tc is not None:
            return res, tc.dump()
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

        trace(tc, "bg", bg)
        trace(tc, "delta", delta)

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
                trace(tc, "bg_converted_mmol", bg)
            try:
                if bg is not None:
                    eventualBG = bg + (delta * 30.0)
                else:
                    eventualBG = None
            except Exception:
                eventualBG = None

            if eventualBG is None or eventualBG <= 0:
                auto_isf_consoleLog.append(
                    f"Projected eventualBG invalid ({eventualBG}), falling back to current BG {bg}"
                )
                eventualBG = bg

        trace(tc, "eventualBG", eventualBG)

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
                sens_ratio_rt = (
                    rt_obj.get("sensitivityRatio")
                    or rt_obj.get("sensitivity_ratio")
                    or rt_obj.get("sensitivityRatioValue")
                )
                if sens_ratio_rt is not None:
                    sens_ratio_rt = float(sens_ratio_rt)
            if sens_ratio_rt:
                autosens_ratio = float(sens_ratio_rt)
                auto_isf_consoleLog.append(f"Using sensitivityRatio from rt: {autosens_ratio:.3f}")
        except Exception:
            logger.exception("autoisf_algorithm: suppressed exception in duration calculation")

        trace(tc, "autosens_ratio", autosens_ratio)

        # effective sensitivity (rounded to reduce floating noise)
        prof_sens = getattr(profile, "variable_sens", None) or getattr(profile, "sens", None)
        if prof_sens is None or prof_sens == 0:
            prof_sens = 6.0
        prof_sens = round(float(prof_sens), 3)
        effective_sens = round(prof_sens * autosens_ratio, 4)
        if effective_sens == 0:
            effective_sens = prof_sens or 6.0

        trace(tc, "prof_sens", prof_sens)
        trace(tc, "effective_sens", effective_sens)

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
            logger.exception("autoisf_algorithm: suppressed exception in sensitivityRatio")

        try:
            if currenttemp is not None:
                dur = int(getattr(currenttemp, "duration", 0) or 0)
                if dur > 0:
                    duration = max(duration, dur)
        except Exception:
            logger.exception("autoisf_algorithm: suppressed exception in duration fallback")

        if loop_wanted_smb and loop_wanted_smb != "none":
            duration = max(duration, 60)

        trace(tc, "duration", duration)

        # --- RT pre-checks (новый парсер) ---
        parsed_rt = parse_rt_to_dict(rt_obj)
        trace(tc, "parsed_rt", parsed_rt)

        # Если нашли low-temp rate — используем его как RT rate
        lowtemp = extract_lowtemp_rate(parsed_rt)
        trace(tc, "lowtemp_rate", lowtemp)
        if lowtemp is not None:
            parsed_rt["rate"] = lowtemp
            auto_isf_consoleLog.append(f"Parsed low-temp rate from RT: {lowtemp:.3f} U/h")

        # Флаг отключения базала
        rt_disable_basal = False
        raw_text = parsed_rt.get("_raw_text", "")

        # Признаки отключения SMB / zero-temp
        if any(
            x in raw_text
            for x in [
                "disable smb",
                "disabling smb",
                "zero temp",
                "low temp",
                "microbolus",
                "min guard",
                "projected below",
            ]
        ):
            rt_disable_basal = True
            auto_isf_consoleLog.append("RT indicates SMB disabled / zero-temp → forcing basal=0 later")

        trace(tc, "rt_disable_basal", rt_disable_basal)
        # --- end RT pre-checks ---

        # insulin requirement (U) - compute after duration so rt.rate/ins can be used if present
        target_bg = getattr(profile, "target_bg", None) or 6.4
        trace(tc, "target_bg", target_bg)

        insulinReq = None

        try:
            if eventualBG is not None:
                insulinReq = (eventualBG - target_bg) / effective_sens
            else:
                insulinReq = None
        except Exception:
            insulinReq = None

        trace(tc, "insulinReq_raw", insulinReq)

        # compute raw rate (U/h) with safeguards
        rate = 0.0
        try:
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

            trace(tc, "rt_rate_val", rt_rate_val)

            if insulinReq is None:
                raw_rate = 0.0
            else:
                if float(insulinReq) <= 0.0 and rt_rate_val is None:
                    raw_rate = 0.0
                else:
                    if rt_rate_val is not None:
                        raw_rate = float(rt_rate_val)
                        auto_isf_consoleLog.append(
                            f"Using RT explicit rate as raw_rate: {raw_rate:.3f} U/h (skip delta cap and SMB scaling)"
                        )
                    else:
                        raw_rate = float(insulinReq) * (60.0 / max(1, duration))

            max_basal = getattr(profile, "max_basal", None)
            if max_basal is not None:
                raw_rate = min(raw_rate, float(max_basal))

            trace(tc, "raw_rate_after_max_basal", raw_rate)

            if rt_rate_val is None:
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

                trace(tc, "allowed_max", allowed_max)
                trace(tc, "raw_rate_after_allowed_max", raw_rate)

            smb_threshold = 1.0
            if (
                insulinReq is not None
                and abs(insulinReq) < smb_threshold
                and getattr(profile, "enableSMB_always", False)
            ):
                smb_ratio_local = getattr(profile, "smb_delivery_ratio", smb_ratio or 0.5)
                raw_rate = raw_rate * float(smb_ratio_local)
                trace(tc, "raw_rate_after_smb_scaling", raw_rate)
            else:
                auto_isf_consoleLog.append(
                    "RT rate present — delta cap and SMB scaling skipped to preserve RT decision"
                )

            rt_rate_provided_flag_check = None
            try:
                # parsed_rt всегда dict, поэтому проверяем только его
                rt_rate_provided_flag_check = parsed_rt.get("rate") or parsed_rt.get("deliveryRate")
            except Exception:
                rt_rate_provided_flag_check = None

            trace(tc, "rt_rate_provided_flag_check", rt_rate_provided_flag_check)

            if (
                insulinReq is not None
                and insulinReq == 0.0
                and not rt_disable_basal
                and not rt_rate_provided_flag_check
            ):
                raw_rate = 0.0
                auto_isf_consoleLog.append("insulinReq==0.0 and no RT rate provided — forcing raw_rate=0.0")
                trace(tc, "raw_rate_forced_zero_by_insulinReq", raw_rate)

            final_rate_source = "computed"

            if (
                isinstance(parsed_rt, dict) and (parsed_rt.get("rate") or parsed_rt.get("deliveryRate")) is not None
            ) or (
                rt_obj and isinstance(rt_obj, dict) and (rt_obj.get("rate") or rt_obj.get("deliveryRate")) is not None
            ):
                final_rate_source = "rt_rate"

            trace(tc, "final_rate_source", final_rate_source)

            trace(tc, "final_rate_source", final_rate_source)

            auto_isf_consoleLog.append(
                f"Final rate decision (pre-clamp): raw_rate={raw_rate:.3f} source={final_rate_source}"
            )

            try:
                if insulinReq is not None and abs(insulinReq) < smb_threshold:
                    insulinReq = round(float(insulinReq), 3)
                trace(tc, "insulinReq_rounded", insulinReq)

                raw_rate = round(float(raw_rate), 3)
                trace(tc, "raw_rate_rounded", raw_rate)

                if max_basal is not None:
                    raw_rate = min(raw_rate, float(max_basal))
                    trace(tc, "raw_rate_after_max_basal_final", raw_rate)

                try:
                    if rt_rate_val is None:
                        raw_rate = min(raw_rate, allowed_max)
                        trace(tc, "raw_rate_after_allowed_max_final", raw_rate)
                except Exception:
                    logger.exception("autoisf_algorithm: suppressed exception in final_rate rounding")

                final_rate = max(0.0, raw_rate)
                rate = round(final_rate, 2)
                trace(tc, "final_rate", rate)

                auto_isf_consoleLog.append(
                    f"Final rate after rounding/clamps: rate={rate:.2f} U/h (raw={raw_rate:.3f})"
                )
            except Exception:
                rate = max(0.0, raw_rate)
                trace(tc, "final_rate_exception_fallback", rate)
        except Exception:
            rate = 0.0
            trace(tc, "final_rate_exception_total", rate)

        try:
            if "rt_disable_basal" in locals() and rt_disable_basal:
                auto_isf_consoleLog.append(
                    "Enforcing RT disable: overriding final rate -> 0.0 U/h (insulinReq preserved)"
                )
                rate = 0.0
                trace(tc, "final_rate_rt_disable_basal", rate)
        except Exception:
            logger.exception("autoisf_algorithm: suppressed exception in RT disable basal")

        res.eventualBG = eventualBG
        res.insulinReq = insulinReq
        res.rate = rate
        res.duration = duration

        trace(tc, "result.eventualBG", res.eventualBG)
        trace(tc, "result.insulinReq", res.insulinReq)
        trace(tc, "result.rate", res.rate)
        trace(tc, "result.duration", res.duration)

        bg_str = f"{bg:.2f}" if (bg is not None) else "None"
        ev_str = f"{eventualBG:.2f}" if (eventualBG is not None) else "None"
        ins_str = f"{insulinReq:.3f}" if (insulinReq is not None) else "None"

        auto_isf_consoleLog.append(
            f"AutoISF calc: bg={bg_str}, delta={delta:.3f}, eventualBG={ev_str}, "
            f"prof_sens={prof_sens:.3f}, autosens_ratio={autosens_ratio:.3f}, effective_sens={effective_sens:.3f}, "
            f"insulinReq={ins_str}, duration={duration}, rate={rate:.3f}"
        )

        if trace_mode and tc is not None:
            return res, tc.dump()
        return res

    except Exception as e:
        auto_isf_consoleError.append(f"Exception in determine_basal_autoisf: {e}")
        if trace_mode and tc is not None:
            return res, tc.dump()
        return res
