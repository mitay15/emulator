from dataclasses import dataclass


@dataclass
class InsulinEvent:
    timestamp: int  # ms
    amount: float  # bolus units
    duration: int  # minutes (for temp basal)
    rate: float  # U/h for temp basal
    type: str  # "bolus" or "temp"


# --- OpenAPS insulin activity curve ---
# DIA = duration of insulin action (hours)
# t = minutes since insulin delivery
def iob_curve(t, dia):
    # t in minutes
    if t < 0 or t > dia * 60:
        return 0.0

    # OpenAPS polynomial curve
    # https://github.com/openaps/oref0/blob/master/lib/iob.js
    # activity = 2 * (t / dia)^3 - 3 * (t / dia)^2 + 1
    x = t / (dia * 60.0)
    activity = 2 * (x**3) - 3 * (x**2) + 1
    return max(activity, 0.0)


def insulin_activity(t, dia):
    # derivative of the curve (mg/dL impact)
    if t < 0 or t > dia * 60:
        return 0.0

    x = t / (dia * 60.0)
    # derivative of polynomial
    d = (6 * x**2 - 6 * x) / (dia * 60.0)
    return max(d, 0.0)


# --- Main IOB calculation ---
def calculate_iob(events, now_ts, dia_hours):
    total_iob = 0.0
    total_activity = 0.0

    for ev in events:
        dt_min = (now_ts - ev.timestamp) / 60000.0  # ms → minutes

        if ev.type == "bolus":
            iob = ev.amount * iob_curve(dt_min, dia_hours)
            act = ev.amount * insulin_activity(dt_min, dia_hours)

        elif ev.type == "temp":
            # convert temp basal to equivalent bolus
            delivered = ev.rate * (ev.duration / 60.0)
            iob = delivered * iob_curve(dt_min, dia_hours)
            act = delivered * insulin_activity(dt_min, dia_hours)

        else:
            continue

        total_iob += iob
        total_activity += act

    return total_iob, total_activity
