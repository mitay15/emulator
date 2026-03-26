# aaps_emulator/core/future_iob_engine.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

from aaps_emulator.core.autoisf_structs import IobTotal


@dataclass
class InsulinCurveParams:
    dia_hours: float = 5.0
    step_minutes: int = 5


# --- Oref1 activity(t) exactly as in AAPS (InsulinOref1.kt) ---
def oref1_activity(t_min: float, dia_hours: float) -> float:
    dia = dia_hours * 60.0
    if t_min <= 0 or t_min >= dia:
        return 0.0

    a = 2.0 / dia
    return a * t_min * math.exp(-a * t_min)


# --- Oref1 IOB(t) exactly as in AAPS (InsulinOref1.kt) ---
def oref1_iob(t_min: float, dia_hours: float) -> float:
    dia = dia_hours * 60.0
    if t_min <= 0:
        return 1.0
    if t_min >= dia:
        return 0.0

    a = 2.0 / dia
    return 1.0 - (1.0 + a * t_min) * math.exp(-a * t_min)


def generate_future_iob(
    iob_now: Optional[IobTotal], params: Optional[InsulinCurveParams] = None
) -> List[IobTotal]:

    if params is None:
        params = InsulinCurveParams()

    if iob_now is None:
        return []

    dia_min = params.dia_hours * 60.0
    step_ms = int(params.step_minutes * 60_000)

    base_time = (
        getattr(iob_now, "timestamp", None) or getattr(iob_now, "time", None) or 0
    )

    result: List[IobTotal] = []
    steps = int(dia_min // params.step_minutes)

    # scale factor: AAPS multiplies IOB(t) by current IOB
    iob_scale = float(getattr(iob_now, "iob", 0.0) or 0.0)

    for step in range(steps + 1):
        t_min = step * params.step_minutes

        # exact AAPS Oref1 curves
        activity_val = oref1_activity(t_min, params.dia_hours)
        iob_frac = oref1_iob(t_min, params.dia_hours)

        result.append(
            IobTotal(
                timestamp=int(base_time + step * step_ms),
                iob=float(iob_scale * iob_frac),
                activity=float(activity_val),
                lastBolusTime=getattr(iob_now, "lastBolusTime", 0),
                raw={},
            )
        )

    return result
