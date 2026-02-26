# aaps_emulator/core/eventual_insulin_rate.py

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def mgdl_to_mmol(x: float) -> float:
    return x / 18.0


def mmol_to_mgdl(x: float) -> float:
    return x * 18.0


def combine_pred_curves(preds: dict[str, list[float]]) -> dict[str, Any]:
    """
    Комбинирует предсказания: для каждого шага берёт максимум из ZT, IOB, COB, UAM.
    Возвращает dict:
      - pred_total: список значений (mg/dL)
      - eventual_mgdl: конечное значение (mg/dL)
    """
    lists: list[list[float]] = [
        preds.get("pred_zt", []),
        preds.get("pred_iob", []),
        preds.get("pred_cob", []),
        preds.get("pred_uam", []),
    ]

    max_len = max((len(lst) for lst in lists), default=0)
    pred_total: list[float] = []

    for i in range(max_len):
        vals: list[float] = []
        for lst in lists:
            if i < len(lst):
                try:
                    vals.append(float(lst[i]))
                except Exception as e:
                    logger.debug("eventual_insulin_rate: non-numeric pred value at index %d: %s", i, e)
                    vals.append(0.0)
        pred_total.append(max(vals) if vals else 0.0)

    eventual = pred_total[-1] if pred_total else 0.0
    return {"pred_total": pred_total, "eventual_mgdl": eventual}


def insulin_required_from_eventual(
    eventual_mmol: float | None, target_mmol: float, effective_sens_mmol_per_U: float
) -> float:
    """
    Возвращает требуемые единицы инсулина (U) для снижения eventual_mmol до target_mmol.
    """
    try:
        if eventual_mmol is None:
            return 0.0
        if effective_sens_mmol_per_U == 0:
            return 0.0
        return (float(eventual_mmol) - float(target_mmol)) / float(effective_sens_mmol_per_U)
    except Exception:
        return 0.0


def rate_from_insulinReq(insulinReq_U: float | None, duration_min: int) -> float:
    """
    Переводит insulinReq (U) в скорость U/h.
    """
    try:
        if insulinReq_U is None:
            return 0.0
        if duration_min <= 0:
            return 0.0
        return float(insulinReq_U) * 60.0 / float(duration_min)
    except Exception:
        return 0.0


def apply_basal_limits(rate_U_per_h: float, profile: Any, respect_max_daily: bool = True) -> dict[str, float]:
    """
    Применяет ограничения к рассчитанной скорости (U/h).
    Возвращает словарь с промежуточными значениями.
    """

    try:
        # max_basal
        max_basal_raw = getattr(profile, "max_basal", None)
        if max_basal_raw is None and isinstance(profile, dict):
            max_basal_raw = profile.get("max_basal")

        try:
            max_basal = float(max_basal_raw) if max_basal_raw is not None else 0.0
        except Exception:
            max_basal = 0.0

        # ограничение по max_basal
        raw_after_max = min(rate_U_per_h, max_basal)

        # current_basal
        current_basal_raw = getattr(profile, "current_basal", None)
        if current_basal_raw is None and isinstance(profile, dict):
            current_basal_raw = profile.get("current_basal", 0.0)

        try:
            current_basal = float(current_basal_raw or 0.0)
        except Exception:
            current_basal = 0.0

        # max_delta_rate
        max_delta_raw = getattr(profile, "max_delta_rate", None)
        if max_delta_raw is None and isinstance(profile, dict):
            max_delta_raw = profile.get("max_delta_rate")

        try:
            max_delta_rate = float(max_delta_raw) if max_delta_raw is not None else 2.0
        except Exception:
            max_delta_rate = 2.0

        allowed_max = current_basal + max_delta_rate

        # ограничение по allowed_max
        raw_after_allowed = min(raw_after_max, allowed_max)

        # max_daily_basal
        max_daily_raw = getattr(profile, "max_daily_basal", None)
        if max_daily_raw is None and isinstance(profile, dict):
            max_daily_raw = profile.get("max_daily_basal")

        if respect_max_daily and max_daily_raw is not None:
            try:
                final_rate = min(raw_after_allowed, float(max_daily_raw))
            except Exception:
                final_rate = raw_after_allowed
        else:
            final_rate = raw_after_allowed

        return {
            "raw_rate": round(float(rate_U_per_h), 6),
            "raw_rate_after_max_basal": round(float(raw_after_max), 6),
            "allowed_max": round(float(allowed_max), 6),
            "raw_rate_after_allowed_max": round(float(raw_after_allowed), 6),
            "final_rate": round(float(final_rate), 6),
        }

    except Exception:
        return {
            "raw_rate": round(float(rate_U_per_h or 0.0), 6),
            "raw_rate_after_max_basal": 0.0,
            "allowed_max": 0.0,
            "raw_rate_after_allowed_max": 0.0,
            "final_rate": 0.0,
        }
