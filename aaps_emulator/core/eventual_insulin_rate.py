# aaps_emulator/core/eventual_insulin_rate.py
import logging
from typing import Any

logger = logging.getLogger(__name__)


def mgdl_to_mmol(x: float) -> float:
    return x / 18.0


def mmol_to_mgdl(x: float) -> float:
    return x * 18.0


def combine_pred_curves(preds: dict[str, list[float]]) -> dict[str, object]:
    """
    Комбинирует предсказания: для каждого шага берёт максимум из ZT, IOB, COB, UAM.
    Возвращает dict с:
      - pred_total: список значений (mg/dL)
      - eventual_mgdl: конечное значение (mg/dL)
    Если входные списки разной длины, отсутствующие значения считаются 0.0.
    """
    lists = [preds.get(k, []) for k in ("pred_zt", "pred_iob", "pred_cob", "pred_uam")]
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
    Возвращает требуемые единицы инсулина (U) для снижения eventual_mmol до target_mmol,
    используя чувствительность effective_sens_mmol_per_U (mmol/L per U).
    Если eventual_mmol is None, возвращает 0.0.
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
    Переводит insulinReq (U) в скорость U/h, распределяя инсулин равномерно по duration_min.
    Если insulinReq_U is None, возвращает 0.0.
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

    Логика:
      - raw_rate_after_max_basal = min(rate, profile.max_basal)
      - allowed_max = profile.current_basal + max_delta_rate (fallback 2.0)
      - raw_rate_after_allowed_max = min(rate, allowed_max)
      - final_rate = raw_rate_after_allowed_max (если respect_max_daily и max_daily задан — min с max_daily)

    Возвращает словарь с промежуточными значениями (округлёнными до 6 знаков).
    """
    try:
        max_basal = getattr(profile, "max_basal", None)
        try:
            max_basal_val = float(max_basal) if max_basal is not None else 0.0
        except Exception:
            max_basal_val = 0.0
        raw_after_max = min(rate_U_per_h, max_basal_val)
        max_daily = getattr(profile, "max_daily_basal", None)
        if max_daily is None and isinstance(profile, dict):
            try:
                max_daily = profile.get("max_daily_basal")
            except Exception:
                max_daily = None

        current_basal = getattr(profile, "current_basal", None)
        if current_basal is None and isinstance(profile, dict):
            current_basal = profile.get("current_basal", 0.0)
        current_basal = float(current_basal or 0.0)

        profile_max_delta = getattr(profile, "max_delta_rate", None)
        if profile_max_delta is None and isinstance(profile, dict):
            profile_max_delta = profile.get("max_delta_rate", None)
        try:
            max_delta_rate = float(profile_max_delta) if profile_max_delta is not None else 2.0
        except Exception:
            max_delta_rate = 2.0

        allowed_max = current_basal + max_delta_rate

        # Применяем ограничение по max_basal первым (всегда)
        raw_after_max = min(rate_U_per_h, float(max_basal))

        # Затем ограничение по allowed_max (current_basal + max_delta_rate),
        # но не выше max_basal
        raw_after_allowed = min(raw_after_max, allowed_max)

        # Финальная скорость: если respect_max_daily и max_daily задан — учитываем его,
        # иначе используем raw_after_allowed. В любом случае final не превысит max_basal.
        if respect_max_daily and max_daily is not None:
            try:
                final = min(raw_after_allowed, float(max_daily))
            except Exception:
                final = raw_after_allowed
        else:
            final = raw_after_allowed

        return {
            "raw_rate": round(float(rate_U_per_h), 6),
            "raw_rate_after_max_basal": round(float(raw_after_max), 6),
            "allowed_max": round(float(allowed_max), 6),
            "raw_rate_after_allowed_max": round(float(raw_after_allowed), 6),
            "final_rate": round(float(final), 6),
        }
    except Exception:
        # В случае ошибки возвращаем безопасные значения
        return {
            "raw_rate": round(float(rate_U_per_h or 0.0), 6),
            "raw_rate_after_max_basal": 0.0,
            "allowed_max": 0.0,
            "raw_rate_after_allowed_max": 0.0,
            "final_rate": 0.0,
        }
