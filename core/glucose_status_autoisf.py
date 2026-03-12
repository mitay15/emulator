# aaps_emulator/core/glucose_status_autoisf.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

from .autoisf_structs import GlucoseStatusAutoIsf


@dataclass
class BucketedEntry:
    timestamp: int
    value: float
    recalculated: float
    filledGap: bool = False


def compute_glucose_status_autoisf(
    data: List[BucketedEntry],
) -> Optional[GlucoseStatusAutoIsf]:
    """
    Port of AAPS GlucoseStatusCalculatorAutoIsf.
    data: list newest->oldest (index 0 is newest)
    """
    if not data:
        return None

    now = data[0]
    now_ts = now.timestamp

    if len(data) == 1:
        return GlucoseStatusAutoIsf(
            glucose=now.recalculated,
            delta=0.0,
            shortAvgDelta=0.0,
            longAvgDelta=0.0,
            date=now_ts,
            duraISFminutes=0.0,
            duraISFaverage=now.value,
            parabolaMinutes=0.0,
            deltaPl=0.0,
            deltaPn=0.0,
            bgAcceleration=0.0,
            a0=now.value,
            a1=0.0,
            a2=0.0,
            corrSqu=0.0,
        )

    # DURA-ISF
    bw = 0.05
    sum_bg = now.recalculated
    old_avg = sum_bg
    minutes_dur = 0
    n = 1

    for i in range(1, len(data)):
        e = data[i]
        if e.value <= 39 or e.filledGap:
            continue
        n += 1
        dt_min = int((now_ts - e.timestamp) / 60000)
        if dt_min - minutes_dur > 13:
            break
        if old_avg * (1 - bw) < e.recalculated < old_avg * (1 + bw):
            sum_bg += e.recalculated
            old_avg = sum_bg / n
            minutes_dur = dt_min
        else:
            break

    duraISFminutes = float(minutes_dur)
    duraISFaverage = old_avg

    # Parabola regression
    if len(data) < 4:
        delta = data[0].recalculated - data[1].recalculated
        return GlucoseStatusAutoIsf(
            glucose=now.recalculated,
            delta=delta,
            shortAvgDelta=delta,
            longAvgDelta=delta,
            date=now_ts,
            duraISFminutes=duraISFminutes,
            duraISFaverage=duraISFaverage,
            parabolaMinutes=0.0,
            deltaPl=0.0,
            deltaPn=0.0,
            bgAcceleration=0.0,
            a0=now.recalculated,
            a1=0.0,
            a2=0.0,
            corrSqu=0.0,
        )

    scale_time = 300.0
    scale_bg = 50.0
    time0 = data[0].timestamp

    sx = sy = sx2 = sx3 = sx4 = sxy = sx2y = 0.0
    ti_last = 0.0
    corr_max = 0.0

    best = dict(a0=0.0, a1=0.0, a2=0.0, duraP=0.0, deltaPl=0.0, deltaPn=0.0, bgAcc=0.0)

    n = 0
    eps = 1e-12
    for i, e in enumerate(data):
        if e.recalculated <= 39 or e.filledGap:
            continue
        n += 1
        # compute normalized time relative to time0
        ti = (e.timestamp - time0) / 1000.0 / scale_time
        age_min = (time0 - e.timestamp) / 60000.0
        if age_min > 47 * 60:
            break
        if ti < ti_last - 11 * 60 / scale_time:
            break
        ti_last = ti
        bg = e.recalculated / scale_bg
        sx += ti
        sy += bg
        sx2 += ti**2
        sx3 += ti**3
        sx4 += ti**4
        sxy += ti * bg
        sx2y += (ti**2) * bg

        if n < 4:
            continue

        detH = (
            sx4 * (sx2 * n - sx * sx)
            - sx3 * (sx3 * n - sx * sx2)
            + sx2 * (sx3 * sx - sx2 * sx2)
        )
        if abs(detH) < eps:
            continue

        detA = (
            sx2y * (sx2 * n - sx * sx)
            - sxy * (sx3 * n - sx * sx2)
            + sy * (sx3 * sx - sx2 * sx2)
        )
        detB = (
            sx4 * (sxy * n - sy * sx)
            - sx3 * (sx2y * n - sy * sx2)
            + sx2 * (sx2y * sx - sxy * sx2)
        )
        detC = (
            sx4 * (sx2 * sy - sx * sxy)
            - sx3 * (sx3 * sy - sx * sx2y)
            + sx2 * (sx3 * sxy - sx2 * sx2y)
        )

        a = detA / detH
        b = detB / detH
        c = detC / detH

        y_mean = sy / n
        s_squares = 0.0
        s_residual = 0.0

        for j in range(i + 1):
            ej = data[j]
            if ej.recalculated <= 39 or ej.filledGap:
                continue
            dt = (ej.timestamp - time0) / 1000.0 / scale_time
            bgj = a * dt**2 + b * dt + c
            s_squares += (ej.recalculated / scale_bg - y_mean) ** 2
            s_residual += (ej.recalculated / scale_bg - bgj) ** 2

        if s_squares <= 0 or not math.isfinite(s_squares):
            r_sq = 0.0
        else:
            r_sq = 1.0 - s_residual / s_squares

        if r_sq >= corr_max:
            corr_max = r_sq
            duraP = -ti * scale_time / 60.0
            delta5 = 5 * 60 / scale_time
            deltaPl = -scale_bg * (a * (-delta5) ** 2 - b * delta5)
            deltaPn = scale_bg * (a * delta5**2 + b * delta5)
            bgAcc = 2 * a * scale_bg
            best = dict(
                a0=c * scale_bg,
                a1=b * scale_bg,
                a2=a * scale_bg,
                duraP=duraP,
                deltaPl=deltaPl,
                deltaPn=deltaPn,
                bgAcc=bgAcc,
            )

    if corr_max == 0.0:
        best["a0"] = now.recalculated
        best["a1"] = 0.0
        best["a2"] = 0.0

    delta = data[0].recalculated - data[1].recalculated

    return GlucoseStatusAutoIsf(
        glucose=now.recalculated,
        delta=delta,
        shortAvgDelta=delta,
        longAvgDelta=delta,
        date=now_ts,
        duraISFminutes=duraISFminutes,
        duraISFaverage=duraISFaverage,
        parabolaMinutes=best["duraP"],
        deltaPl=best["deltaPl"],
        deltaPn=best["deltaPn"],
        bgAcceleration=best["bgAcc"],
        a0=best["a0"],
        a1=best["a1"],
        a2=best["a2"],
        corrSqu=corr_max,
    )
