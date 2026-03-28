# aaps_emulator/core/future_iob_engine.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

from aaps_emulator.core.autoisf_structs import IobTotal


# ---------------------------------------------------------
# ПАРАМЕТРЫ Oref1
# ---------------------------------------------------------
@dataclass
class InsulinCurveParams:
    dia_hours: float = 5.0
    step_minutes: int = 5


# ---------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ---------------------------------------------------------
def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


# ---------------------------------------------------------
# Oref1 activity(t) и IOB(t)
# ---------------------------------------------------------
def _oref1_coeff(dia_hours: float) -> float:
    """Коэффициент a = 2/dia для обеих кривых."""
    dia = dia_hours * 60.0
    return 2.0 / dia if dia > 0 else 0.0


def oref1_activity(t_min: float, dia_hours: float) -> float:
    dia = dia_hours * 60.0
    if t_min <= 0 or t_min >= dia:
        return 0.0

    a = _oref1_coeff(dia_hours)
    return a * t_min * math.exp(-a * t_min)


def oref1_iob(t_min: float, dia_hours: float) -> float:
    dia = dia_hours * 60.0
    if t_min <= 0:
        return 1.0
    if t_min >= dia:
        return 0.0

    a = _oref1_coeff(dia_hours)
    return 1.0 - (1.0 + a * t_min) * math.exp(-a * t_min)


# ---------------------------------------------------------
# ГЕНЕРАЦИЯ БУДУЩИХ IOB‑ТИКОВ
# ---------------------------------------------------------
def generate_future_iob(
    iob_now: Optional[IobTotal], params: Optional[InsulinCurveParams] = None
) -> List[IobTotal]:

    if params is None:
        params = InsulinCurveParams()

    if iob_now is None:
        return []

    dia_min = params.dia_hours * 60.0
    step_ms = int(params.step_minutes * 60_000)

    # безопасный timestamp
    base_time = _safe_int(
        getattr(iob_now, "timestamp", None)
        or getattr(iob_now, "time", None),
        0,
    )

    # масштабирование IOB(t)
    iob_scale = _safe_float(getattr(iob_now, "iob", 0.0), 0.0)

    steps = int(dia_min // params.step_minutes)
    result: List[IobTotal] = []

    for step in range(steps + 1):
        t_min = step * params.step_minutes

        activity_val = oref1_activity(t_min, params.dia_hours)
        iob_frac = oref1_iob(t_min, params.dia_hours)

        result.append(
            IobTotal(
                timestamp=base_time + step * step_ms,
                iob=iob_scale * iob_frac,
                activity=activity_val,
                lastBolusTime=_safe_int(getattr(iob_now, "lastBolusTime", 0), 0),
            )
        )

    return result
