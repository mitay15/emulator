# aaps_emulator/core/cob_uam_pred.py

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_pred_from_rt_lists(rt: dict[str, Any]) -> dict[str, list[float]]:
    """
    Возвращает предсказания из RT (если есть) в mg/dL.
    Ключи: pred_iob, pred_cob, pred_uam, pred_zt.
    Все значения приводятся к спискам float.
    """

    def _to_float_list(val: Any) -> list[float]:
        if not isinstance(val, (list, tuple)):
            return []
        out: list[float] = []
        for x in val:
            try:
                out.append(float(x))
            except Exception as e:
                logger.debug("cob_uam_pred: non-numeric value ignored: %s", e)
                continue

    pred_iob = _to_float_list(rt.get("pred_iob") or rt.get("predIOB"))
    pred_cob = _to_float_list(rt.get("pred_cob") or rt.get("predCOB"))
    pred_uam = _to_float_list(rt.get("pred_uam") or rt.get("predUAM"))
    pred_zt = _to_float_list(rt.get("pred_zt") or rt.get("predZT"))

    return {
        "pred_iob": pred_iob,
        "pred_cob": pred_cob,
        "pred_uam": pred_uam,
        "pred_zt": pred_zt,
    }


def simple_cob_absorption(meal_cob_g: float, cat_hours: float = 2.0, step_minutes: int = 5) -> dict[str, Any]:
    """
    Простая модель распределения углеводов по CAT (равномерно).
    Возвращает:
      - pred_cob: список накопленных граммов по шагам,
      - ci_per_5m: грамм/шаг,
      - cob_g: исходное количество углеводов.
    """
    if meal_cob_g <= 0:
        return {"pred_cob": [], "ci_per_5m": 0.0, "cob_g": 0.0}

    steps = int((cat_hours * 60) / step_minutes)
    if steps <= 0:
        return {"pred_cob": [], "ci_per_5m": 0.0, "cob_g": meal_cob_g}

    per_step_g = meal_cob_g / steps
    pred_cob: list[float] = []
    cum = 0.0

    for _ in range(steps):
        cum += per_step_g
        pred_cob.append(cum)

    return {
        "pred_cob": pred_cob,
        "ci_per_5m": per_step_g,
        "cob_g": meal_cob_g,
    }


def build_uam_pred(uam_impact_mg_per_5m: float, uam_duration_hours: float, step_minutes: int = 5) -> list[float]:
    """
    Треугольная модель UAM (mg/dL per 5m).
    Возвращает список значений UAM по шагам.
    """
    if uam_impact_mg_per_5m <= 0 or uam_duration_hours <= 0:
        return []

    steps = int((uam_duration_hours * 60) / step_minutes)
    if steps <= 0:
        return []

    peak = float(uam_impact_mg_per_5m)
    pred: list[float] = []

    # Треугольная форма: максимум в середине
    mid = steps / 2.0

    for i in range(steps):
        frac = 1.0 - abs((i - mid) / mid)
        val = max(0.0, peak * frac)
        pred.append(val)

    return pred
