# aaps_emulator/core/iob_openaps.py


class InsulinEventSimple:
    def __init__(self, timestamp: int, amount: float, duration: int = 0, rate: float = 0.0, type: str = "bolus"):
        self.timestamp = int(timestamp)
        self.amount = float(amount)
        self.duration = int(duration)
        self.rate = float(rate)
        self.type = type


def compute_iob_openaps(events: list[InsulinEventSimple], now_ts: int, dia_hours: float = 4.0):
    """
    Простая реализация IOB в стиле OpenAPS.
    Возвращает dict { iob: float (U), activity: float (U/hr) }.
    """
    if not events:
        return {"iob": 0.0, "activity": 0.0}

    dia_ms = dia_hours * 3600.0 * 1000.0
    total_iob = 0.0
    total_activity = 0.0

    for e in events:
        if e.type == "bolus" and e.amount > 0:
            elapsed = now_ts - e.timestamp
            if elapsed < 0:
                elapsed = 0
            if elapsed >= dia_ms:
                rem = 0.0
            else:
                rem = e.amount * (1.0 - (elapsed / dia_ms))
            activity = (e.amount / dia_hours) * max(0.0, 1.0 - (elapsed / dia_ms))
            total_iob += rem
            total_activity += activity

        if e.type == "temp" and e.rate is not None and e.duration:
            end_ts = e.timestamp + int(e.duration * 60 * 1000)
            if now_ts >= end_ts:
                continue
            remaining_ms = end_ts - now_ts
            remaining_hours = remaining_ms / (3600.0 * 1000.0)
            rem = e.rate * remaining_hours
            activity = e.rate
            total_iob += rem
            total_activity += activity

    return {"iob": round(total_iob, 6), "activity": round(total_activity, 6)}
