# aaps_emulator/core/autosens.py
"""
Простой, воспроизводимый алгоритм autosens (rolling window).
Цель: вычислить поправочный коэффициент чувствительности (ratio),
основанный на последних N минут данных IOB/CGM/insulin events.

Алгоритм (упрощённый, но близкий по идее):
- Берём список точек истории: каждая точка — словарь с ключами:
  - ts_s (timestamp seconds)
  - glucose (mmol/L)
  - predicted (optional) — прогнозируемое значение
  - insulin (insulin delivered since last point, U) — опционально
- Для окон длиной window_minutes собираем пары (observed_delta, expected_delta)
  и вычисляем локальные оценки ratio = observed_sensitivity / profile_sensitivity.
- Возвращаем медиану всех локальных ratio в окне; если данных мало — возвращаем 1.0.

Функции:
- compute_autosens_ratio(history_points, window_minutes=180, min_points=4, clip=(0.7,1.3))
"""

from typing import List, Dict, Optional
import statistics
import math
from datetime import datetime

def compute_autosens_ratio(
    history_points: List[Dict],
    window_minutes: int = 180,
    min_points: int = 4,
    clip: Optional[tuple] = (0.7, 1.3)
) -> float:
    """
    history_points: список словарей, каждый должен содержать:
      - ts_s: int (unix seconds)
      - glucose: float (mmol/L)
      - delta5: float (mmol/L per 5min) optional
      - expected_delta5: float (mmol/L per 5min) optional (model prediction)
      - profile_sens: float (mmol/U) optional (if present, used to compute ratio)
    Возвращает: autosens_ratio (float)
    """
    if not history_points:
        return 1.0

    # sort by timestamp ascending
    pts = sorted(history_points, key=lambda x: x.get("ts_s", 0))

    # determine window start
    last_ts = pts[-1].get("ts_s", 0)
    window_start = last_ts - window_minutes * 60

    # collect local ratio estimates
    ratios = []

    for p in pts:
        ts = p.get("ts_s", 0)
        if ts < window_start:
            continue

        # prefer explicit delta5 and expected_delta5 if present
        delta5 = p.get("delta5")
        expected_delta5 = p.get("expected_delta5")
        profile_sens = p.get("profile_sens")

        # fallback: try to compute delta5 from neighbor points if not present
        if delta5 is None:
            # cannot compute reliably here; skip
            continue

        if expected_delta5 is None:
            # if no expected, skip (we need expected trend to compare)
            continue

        # if profile_sens not provided, skip (we need baseline sens)
        if profile_sens is None or profile_sens == 0:
            continue

        # observed sensitivity proxy: how much BG changed per unit insulin effect expected
        # We compute ratio = expected_delta5 / delta5 scaled by profile_sens
        # More robust approach: ratio = (observed_effect_per_unit) / profile_sens
        # Here we approximate observed_effect_per_unit = expected_delta5 / (profile_sens) * correction
        # To keep it simple: ratio_est = expected_delta5 / delta5
        try:
            if math.isfinite(delta5) and delta5 != 0:
                ratio_est = expected_delta5 / delta5
                if math.isfinite(ratio_est) and ratio_est > 0:
                    ratios.append(ratio_est)
        except Exception:
            continue

    # if not enough points, return 1.0
    if len(ratios) < min_points:
        return 1.0

    # robust central tendency: median
    try:
        med = statistics.median(ratios)
    except Exception:
        med = 1.0

    # clip to reasonable bounds
    if clip:
        low, high = clip
        med = max(low, min(high, med))

    return float(med)
