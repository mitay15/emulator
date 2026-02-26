# aaps_emulator/core/autoisf_algorithm.py
"""
AutoISF algorithm utilities.

Этот модуль даёт «защитную» реализацию determine_basal_autoisf, которая:
 - принимает опциональный rt (runtime) и вытаскивает eventualBG, если он есть
 - безопасно обрабатывает отсутствие bg/delta
 - использует autosens ratio и sensitivityRatio из rt, если они есть
 - при необходимости конвертирует mg/dL -> mmol/L
 - считает insulinReq и переводит его в rate с защитами (duration, SMB scaling, лимиты)
 - приоритетно уважает insulinReq/rate из RT и сигналы RT об отключении SMB/базала
 - возвращает AutoIsfResult(eventualBG, insulinReq, rate, duration)
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from aaps_emulator.core.cob_uam_pred import (
    build_pred_from_rt_lists,
    build_uam_pred,
    simple_cob_absorption,
)
from aaps_emulator.core.eventual_insulin_rate import (
    apply_basal_limits,
    combine_pred_curves,
    insulin_required_from_eventual,
    mgdl_to_mmol,
    rate_from_insulinReq,
)
from aaps_emulator.core.iob_openaps import InsulinEventSimple, compute_iob_openaps
from aaps_emulator.core.rt_parser import extract_lowtemp_rate, parse_rt_to_dict

logger = logging.getLogger(__name__)


@dataclass
class AutoIsfResult:
    eventualBG: float | None
    insulinReq: float | None
    rate: float
    duration: int


class TraceCollector:
    def __init__(self) -> None:
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
    Пытаемся вытащить eventualBG из rt (dict или строка).
    Возвращаем eventualBG в mmol/L или None.

    Обрабатываем:
      - dict с ключами 'eventualBG', 'eventual_bg', 'eventual'
      - dict с 'predBGs' / 'predictions' / 'preds'
      - строку с 'eventualBG=NNN' или 'eventual bg 14,2'

    Если значение похоже на mg/dL (>30), делим на 18.
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

    # string-like rt
    try:
        s = str(rt_obj)
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
    glucose_status: Any,
    currenttemp: Any,
    iob_data_array: list[Any] | None,
    profile: Any,
    autosens_data: Any,
    meal_data: Any,
    rt: Any = None,
    microBolusAllowed: bool = False,
    currentTime: int = 0,
    flatBGsDetected: bool = False,
    autoIsfMode: bool = True,
    loop_wanted_smb: str = "none",
    profile_percentage: int = 100,
    smb_ratio: float = 0.5,
    smb_max_range_extension: float = 1.0,
    iob_threshold_percent: int = 100,
    auto_isf_consoleError: list[str] | None = None,
    auto_isf_consoleLog: list[str] | None = None,
    trace_mode: bool = False,
) -> AutoIsfResult | tuple[AutoIsfResult, list[tuple[str, Any]]]:
    """
    Defensive AutoISF calculation.
    """
    tc: TraceCollector | None = TraceCollector() if trace_mode else None

    # нормализуем rt в dict со snake_case и mmol
    try:
        from aaps_emulator.parsing.rt_parser import normalize_rt

        if rt is not None:
            rt = normalize_rt(rt)
    except Exception as exc:
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
        # bg и delta
        try:
            bg: float | None = getattr(glucose_status, "glucose", None)
        except Exception:
            bg = None
        try:
            delta_raw = getattr(glucose_status, "delta", 0.0)
            delta: float = float(delta_raw)
        except Exception:
            delta = 0.0

        trace(tc, "bg", bg)
        trace(tc, "delta", delta)

        # 1) eventualBG из rt
        eventualBG: float | None = None
        rt_obj: Any = rt

        if rt_obj:
            ev_from_rt = _extract_predicted_eventual_from_rt(rt_obj)
            if ev_from_rt is not None:
                eventualBG = ev_from_rt
                auto_isf_consoleLog.append(f"Using predicted eventualBG from rt: {eventualBG:.3f} mmol/L")

        # 2) fallback: bg + delta*30
        if eventualBG is None:
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

        # --- RT pre-checks and duration calculation (keep before diagnostics) ---
        parsed_rt: dict[str, Any] = parse_rt_to_dict(rt_obj)
        trace(tc, "parsed_rt", parsed_rt)

        lowtemp = extract_lowtemp_rate(parsed_rt)
        trace(tc, "lowtemp_rate", lowtemp)
        if lowtemp is not None:
            parsed_rt["rate"] = lowtemp
            auto_isf_consoleLog.append(f"Parsed low-temp rate from RT: {lowtemp:.3f} U/h")

        rt_disable_basal = False
        raw_text = str(parsed_rt.get("_raw_text", ""))

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

        # duration (compute early so diagnostics can use it)
        duration: int = 30
        try:
            if rt_obj and isinstance(rt_obj, dict):
                rt_dur = rt_obj.get("duration") or rt_obj.get("dur")
                if rt_dur is not None:
                    rd = int(float(rt_dur))
                    if rd > 300:
                        rd = max(5, rd // 60)
                    duration = max(5, rd)
                    auto_isf_consoleLog.append(f"Using duration from rt: {duration} minutes")
                else:
                    preds_rt = rt_obj.get("predBGs") or rt_obj.get("predictions")
                    if preds_rt and isinstance(preds_rt, (list, tuple)):
                        duration = max(duration, len(preds_rt) * 5)
        except Exception:
            logger.exception("autoisf_algorithm: suppressed exception in sensitivityRatio")

        try:
            if currenttemp is not None:
                dur_val = getattr(currenttemp, "duration", 0) or 0
                dur_int = int(dur_val)
                if dur_int > 0:
                    duration = max(duration, dur_int)
        except Exception:
            logger.exception("autoisf_algorithm: suppressed exception in duration fallback")

        if loop_wanted_smb and loop_wanted_smb != "none":
            duration = max(duration, 60)

        trace(tc, "duration", duration)
        # --- end RT pre-checks and duration ---

        # ------------------ Диагностический блок predBG / IOB / eventual → insulinReq → rate ------------------
        # Этот блок теперь выполняется после parsed_rt и duration, и помечает все ключи префиксом diagnostic.
        try:
            if isinstance(rt_obj, dict) and rt_obj.get("timestamp") is not None:
                ts_raw = rt_obj.get("timestamp")
                now_ts_ms = int(float(ts_raw))
            else:
                now_ts_ms = int(time.time() * 1000)
        except Exception:
            now_ts_ms = int(time.time() * 1000)

        # IOB OpenAPS (диагностика)
        try:
            simple_events: list[InsulinEventSimple] = []
            for e in iob_data_array or []:
                ts_e = getattr(e, "timestamp", None) or getattr(e, "date", None) or now_ts_ms
                amt = float(getattr(e, "amount", 0.0) or 0.0)
                dur_e = int(getattr(e, "duration", 0) or 0)
                rate_e = float(getattr(e, "rate", 0.0) or 0.0)
                typ = str(getattr(e, "type", "bolus") or "bolus")
                simple_events.append(InsulinEventSimple(ts_e, amt, dur_e, rate_e, typ))
            iob_info = compute_iob_openaps(simple_events, now_ts_ms, dia_hours=4.0)
            trace(tc, "diagnostic.iob_openaps", iob_info.get("iob"))
            trace(tc, "diagnostic.activity_openaps", iob_info.get("activity"))
        except Exception as _e:
            trace(tc, "diagnostic.iob_openaps_error", str(_e))

        # preds from RT or built from meal/profile
        preds: dict[str, Any] = {}
        try:
            preds = build_pred_from_rt_lists(rt_obj or {})
            trace(
                tc, "diagnostic.preds_from_rt_lengths", {k: len(v) for k, v in preds.items() if hasattr(v, "__len__")}
            )
        except Exception:
            preds = {"pred_iob": [], "pred_cob": [], "pred_uam": [], "pred_zt": []}

        # build COB if missing
        ci_per_5m: float = 0.0
        try:
            if not preds.get("pred_cob"):
                if meal_data and getattr(meal_data, "meal_cob", None):
                    cob_model = simple_cob_absorption(
                        meal_cob_g=float(getattr(meal_data, "meal_cob", 0.0) or 0.0),
                        cat_hours=2.0,
                        step_minutes=5,
                    )
                    cr = getattr(profile, "carb_ratio", None)
                    if cr and float(cr) > 0:
                        cr_f = float(cr)
                        sens_mmol = float(getattr(profile, "sens", 4.8) or 4.8)
                        sens_mgdl_per_U = sens_mmol * 18.0
                        mgdl_per_gram = sens_mgdl_per_U / cr_f
                        preds["pred_cob"] = [float(g) * mgdl_per_gram for g in cob_model["pred_cob"]]
                        ci_per_5m = float(cob_model["ci_per_5m"]) * mgdl_per_gram
                    else:
                        preds["pred_cob"] = []
                        ci_per_5m = 0.0
                else:
                    ci_per_5m = 0.0
            else:
                try:
                    pred_cob_list = preds.get("pred_cob", [])
                    if pred_cob_list:
                        ci_per_5m = float(pred_cob_list[0] or 0.0)
                    else:
                        ci_per_5m = 0.0
                except Exception:
                    ci_per_5m = 0.0
            trace(tc, "diagnostic.ci_per_5m", ci_per_5m)
        except Exception as _e:
            trace(tc, "diagnostic.cob_build_error", str(_e))

        # UAM pred
        try:
            if not preds.get("pred_uam"):
                uam_impact: float | None = None
                uam_duration: float | None = None
                if isinstance(rt_obj, dict):
                    uam_impact_raw = rt_obj.get("uam_impact") or rt_obj.get("uamImpact") or rt_obj.get("uamimpact")
                    uam_duration_raw = rt_obj.get("uam_duration_hours") or rt_obj.get("uamDuration")
                    if uam_impact_raw is not None:
                        uam_impact = float(uam_impact_raw)
                    if uam_duration_raw is not None:
                        uam_duration = float(uam_duration_raw)
                if uam_impact is not None:
                    preds["pred_uam"] = build_uam_pred(
                        uam_impact, uam_duration if uam_duration is not None else 3.0, step_minutes=5
                    )
                else:
                    preds["pred_uam"] = []
            trace(tc, "diagnostic.pred_uam_len", len(preds.get("pred_uam", [])))
        except Exception as _e:
            trace(tc, "diagnostic.uam_build_error", str(_e))

        # combine and eventual (diagnostic)
        try:
            combined = combine_pred_curves(preds)
            eventual_mgdl_calc_any = combined.get("eventual_mgdl", 0.0)
            try:
                eventual_mgdl_calc = float(eventual_mgdl_calc_any)
            except (TypeError, ValueError):
                eventual_mgdl_calc = 0.0
            eventual_mmol_calc = mgdl_to_mmol(eventual_mgdl_calc)
            trace(tc, "diagnostic.eventual_mgdl_calc", eventual_mgdl_calc)
            trace(tc, "diagnostic.eventual_mmol_calc", eventual_mmol_calc)
        except Exception as _e:
            eventual_mgdl_calc = None
            eventual_mmol_calc = None
            trace(tc, "diagnostic.combine_pred_error", str(_e))

        # if eventualBG not provided by RT, use diagnostic eventual
        try:
            if eventualBG is None and eventual_mmol_calc is not None:
                eventualBG = eventual_mmol_calc
                trace(tc, "diagnostic.eventualBG_from_combined", eventualBG)
        except Exception as e:
            logger.debug("autoisf_algorithm: suppressed exception in diagnostic.eventualBG_from_combined: %s", e)
            trace(tc, "diagnostic.eventualBG_from_combined_error", str(e))

        # diagnostic insulinReq and rate
        try:
            effective_sens_diag_raw = getattr(profile, "variable_sens", getattr(profile, "sens", 4.8))
            effective_sens_diag = float(effective_sens_diag_raw or 4.8)
            if eventualBG is not None:
                insulinReq_calc = insulin_required_from_eventual(
                    eventualBG, float(getattr(profile, "target_bg", 6.4) or 6.4), effective_sens_diag
                )
            else:
                insulinReq_calc = None
            trace(tc, "diagnostic.insulinReq_calc", insulinReq_calc)

            duration_for_rate = int(getattr(currenttemp, "duration", 30) or 30) if currenttemp else 30
            rate_calc = (
                rate_from_insulinReq(float(insulinReq_calc or 0.0), duration_for_rate)
                if insulinReq_calc is not None
                else 0.0
            )

            # diagnostic limits: raw (no max_daily) and strict (respect max_daily)
            limits_calc = apply_basal_limits(rate_calc, profile, respect_max_daily=False)
            trace(tc, "diagnostic.rate_calc_raw", rate_calc)
            trace(tc, "diagnostic.limits_calc", limits_calc)

            limits_calc_strict = apply_basal_limits(rate_calc, profile, respect_max_daily=True)
            trace(tc, "diagnostic.limits_calc_strict", limits_calc_strict)
        except Exception as _e:
            trace(tc, "diagnostic.insulin_rate_calc_error", str(_e))
        # ------------------ конец диагностического блока ------------------

        # autosens ratio
        autosens_ratio: float = 1.0
        if autosens_data is not None:
            try:
                r = getattr(autosens_data, "ratio", None)
                if r is not None and r != 1.0:
                    autosens_ratio = float(r)
            except Exception:
                autosens_ratio = 1.0

        # sensitivityRatio из rt
        try:
            sens_ratio_rt: float | None = None
            if rt_obj and isinstance(rt_obj, dict):
                sens_ratio_rt_raw = (
                    rt_obj.get("sensitivityRatio")
                    or rt_obj.get("sensitivity_ratio")
                    or rt_obj.get("sensitivityRatioValue")
                )
                if sens_ratio_rt_raw is not None:
                    sens_ratio_rt = float(sens_ratio_rt_raw)
            if sens_ratio_rt is not None:
                autosens_ratio = float(sens_ratio_rt)
                auto_isf_consoleLog.append(f"Using sensitivityRatio from rt: {autosens_ratio:.3f}")
        except Exception:
            logger.exception("autoisf_algorithm: suppressed exception in duration calculation")

        trace(tc, "autosens_ratio", autosens_ratio)

        # чувствительность
        prof_sens_raw = getattr(profile, "variable_sens", None) or getattr(profile, "sens", None)
        if prof_sens_raw is None or prof_sens_raw == 0:
            prof_sens_raw = 6.0
        prof_sens = round(float(prof_sens_raw), 3)
        effective_sens = round(prof_sens * autosens_ratio, 4)
        if effective_sens == 0:
            effective_sens = prof_sens or 6.0

        trace(tc, "prof_sens", prof_sens)
        trace(tc, "effective_sens", effective_sens)

        # target
        target_bg_raw = getattr(profile, "target_bg", None) or 6.4
        target_bg = float(target_bg_raw)
        trace(tc, "target_bg", target_bg)

        insulinReq: float | None = None
        try:
            if eventualBG is not None:
                insulinReq = (eventualBG - target_bg) / effective_sens
            else:
                insulinReq = None
        except Exception:
            insulinReq = None

        trace(tc, "insulinReq_raw", insulinReq)

        # rate
        rate: float = 0.0
        try:
            rt_rate_provided_flag: Any = None
            rt_rate_val: float | None = None
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
                current_basal = float(getattr(profile, "current_basal", 0.0) or 0.0)
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
                and bool(getattr(profile, "enableSMB_always", False))
            ):
                smb_ratio_local = getattr(profile, "smb_delivery_ratio", smb_ratio or 0.5)
                raw_rate = raw_rate * float(smb_ratio_local)
                trace(tc, "raw_rate_after_smb_scaling", raw_rate)
            else:
                auto_isf_consoleLog.append(
                    "RT rate present — delta cap and SMB scaling skipped to preserve RT decision"
                )

            try:
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

            auto_isf_consoleLog.append(
                f"Final rate decision (pre-clamp): raw_rate={raw_rate:.3f} source={final_rate_source}"
            )

            try:
                # округлим insulinReq для логов, если он мал
                if insulinReq is not None and abs(insulinReq) < smb_threshold:
                    insulinReq = round(float(insulinReq), 3)
                trace(tc, "insulinReq_rounded", insulinReq)

                # округлим raw_rate для логов
                raw_rate = round(float(raw_rate), 3)
                trace(tc, "raw_rate_rounded", raw_rate)

                # применяем строгие лимиты для финального решения (учитываем max_daily_basal)
                final_limits = apply_basal_limits(raw_rate, profile, respect_max_daily=True)
                trace(tc, "final_limits_applied", final_limits)

                final_rate_val = final_limits.get("final_rate", 0.0)
                final_rate = float(final_rate_val)
                rate = round(max(0.0, final_rate), 2)
                trace(tc, "final_rate", rate)

                auto_isf_consoleLog.append(f"Final rate after strict clamps: rate={rate:.2f} U/h (raw={raw_rate:.3f})")
            except Exception:
                # fallback: если что-то пошло не так, используем безопасный raw_rate
                rate = max(0.0, raw_rate)
                trace(tc, "final_rate_exception_fallback", rate)

        except Exception:
            rate = 0.0
            trace(tc, "final_rate_exception_total", rate)

        try:
            if rt_disable_basal:
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

        # mark final pred lists (if present) with final. prefix to avoid confusion with diagnostic.*
        try:
            trace(tc, "final.pred_uam_first10", preds.get("pred_uam", [])[:10])
            trace(tc, "final.pred_zt_first10", preds.get("pred_zt", [])[:10])
        except Exception as e:
            logger.debug("autoisf_algorithm: suppressed exception while tracing final preds: %s", e)
            trace(tc, "final.pred_trace_error", str(e))

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
