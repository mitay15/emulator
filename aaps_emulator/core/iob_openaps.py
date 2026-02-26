# aaps_emulator/core/iob_openaps.py

from __future__ import annotations


class InsulinEventSimple:
    def __init__(
        self,
        timestamp: int,
        amount: float,
        duration: int = 0,
        rate: float = 0.0,
        type: str = "bolus",
    ) -> None:
        self.timestamp: int = int(timestamp)
        self.amount: float = float(amount)
        self.duration: int = int(duration)
        self.rate: float = float(rate)
        self.type: str = type


def compute_iob_openaps(events: list[InsulinEventSimple], now_ts: int, dia_hours: float = 4.0) -> dict[str, float]:
    """
    Простая реализация IOB в стиле OpenAPS.
    Возвращает dict { "iob": float (U), "activity": float (U/hr) }.
    """

    if not events:
        return {"iob": 0.0, "activity": 0.0}

    dia_ms: float = dia_hours * 3600.0 * 1000.0
    total_iob: float = 0.0
    total_activity: float = 0.0

    for e in events:
        # --- Bolus insulin ---
        if e.type == "bolus" and e.amount > 0:
            elapsed: float = float(now_ts - e.timestamp)
            if elapsed < 0:
                elapsed = 0.0

            rem = 0.0 if elapsed >= dia_ms else e.amount * (1.0 - elapsed / dia_ms)

            activity = (e.amount / dia_hours) * max(0.0, 1.0 - (elapsed / dia_ms))

            total_iob += rem
            total_activity += activity

        # --- Temp basal ---
        if e.type == "temp" and e.rate is not None and e.duration:
            end_ts = e.timestamp + int(e.duration * 60 * 1000)
            if now_ts >= end_ts:
                continue

            remaining_ms = float(end_ts - now_ts)
            remaining_hours = remaining_ms / (3600.0 * 1000.0)

            rem = e.rate * remaining_hours
            activity = e.rate

            total_iob += rem
            total_activity += activity

    return {
        "iob": round(total_iob, 6),
        "activity": round(total_activity, 6),
    }
