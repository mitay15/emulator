from typing import List, Dict, Any
from parser.timeline import TimelineEvent


def reconstruct_cob_uam(events: List[TimelineEvent]) -> List[Dict[str, Any]]:
    """
    Берём реальные CARBS (из USER ENTRY и Wizard),
    смотрим BG в окне 4 часа, считаем пик и ΔBG на 10g.
    """
    out = []

    meals = [e for e in events if e.kind == "CARBS"]
    bgs = [e for e in events if e.kind == "BG"]

    def bg_series_after(ts_start: int, window_min: int = 240):
        ts_end = ts_start + window_min * 60 * 1000
        return [bg for bg in bgs if ts_start <= bg.ts <= ts_end]

    for meal in meals:
        carbs = meal.data.get("carbs") or 0.0
        ts = meal.ts
        series = bg_series_after(ts)

        if not series or carbs <= 0:
            continue

        bg0 = series[0].data.get("glucose") or series[0].data.get("value")
        bg_max = max(
            (bg.data.get("glucose") or bg.data.get("value") or bg0)
            for bg in series
        )
        delta = bg_max - bg0

        out.append({
            "timestamp": ts,
            "carbs": carbs,
            "bg_start": bg0,
            "bg_peak": bg_max,
            "delta": delta,
            "delta_per_10g": delta / (carbs / 10.0) if carbs > 0 else None,
        })

    return out
