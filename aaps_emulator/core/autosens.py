# aaps_emulator/core/autosens.py
"""
Простой, воспроизводимый алгоритм autosens (rolling window).
"""

from __future__ import annotations

import logging
import math
import statistics
from typing import Any

logger = logging.getLogger(__name__)


def compute_autosens_ratio(
    history_points: list[dict[str, Any]],
    window_minutes: int = 180,
    min_points: int = 4,
    clip: tuple[float, float] | None = (0.7, 1.3),
) -> float:
    """
    history_points: список словарей, каждый должен содержать:
      - ts_s: int (unix seconds)
      - glucose: float (mmol/L)
      - delta5: float (mmol/L per 5min) optional
      - expected_delta5: float (mmol/L per 5min) optional
      - profile_sens: float (mmol/U) optional
    Возвращает autosens_ratio (float).
    """

    if not history_points:
        return 1.0

    # сортировка по времени
    pts = sorted(history_points, key=lambda x: int(x.get("ts_s", 0)))

    last_ts = int(pts[-1].get("ts_s", 0))
    window_start = last_ts - window_minutes * 60

    ratios: list[float] = []

    for p in pts:
        ts = int(p.get("ts_s", 0))
        if ts < window_start:
            continue

        delta5_raw = p.get("delta5")
        expected_raw = p.get("expected_delta5")
        profile_sens_raw = p.get("profile_sens")

        # обязательные параметры
        if delta5_raw is None or expected_raw is None or profile_sens_raw is None:
            continue

        try:
            delta5 = float(delta5_raw)
            expected_delta5 = float(expected_raw)
            profile_sens = float(profile_sens_raw)
        except (TypeError, ValueError):
            continue

        if profile_sens == 0 or delta5 == 0 or not math.isfinite(delta5):
            continue

        try:
            ratio_est = expected_delta5 / delta5
            if math.isfinite(ratio_est) and ratio_est > 0:
                ratios.append(ratio_est)
        except Exception:
            logger.exception("autosens: skipping point due to exception")
            continue

    if len(ratios) < min_points:
        return 1.0

    try:
        med = float(statistics.median(ratios))
    except Exception:
        med = 1.0

    if clip is not None:
        low, high = clip
        med = max(low, min(high, med))

    return med
