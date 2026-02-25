from dataclasses import dataclass


@dataclass
class CarbEvent:
    timestamp: int  # ms
    carbs: float  # grams
    absorption: float  # hours (CAT)


# OpenAPS carb impact model
def carb_impact(t_min, cat_hours, peak=120):
    """
    t_min — minutes since carb intake
    cat_hours — carb absorption time (hours)
    peak — peak absorption (minutes), default 120
    """
    if t_min < 0:
        return 0.0

    cat_min = cat_hours * 60.0
    if t_min > cat_min:
        return 0.0

    # normalized time
    x = t_min / peak

    # parabolic absorption curve
    if x <= 1:
        return 1 - (1 - x) ** 2
    else:
        # tail decay
        tail = (cat_min - t_min) / (cat_min - peak)
        return max(tail, 0.0)


def calculate_cob_curve(events, now_ts, cat_hours):
    """
    Returns:
      cob_g — remaining carbs
      ci — current carb impact (mg/dL per 5m)
      predcis — list of predicted CI for next 48 steps (4 hours)
    """
    total_cob = 0.0
    total_ci = 0.0

    predcis = [0.0] * 48

    for ev in events:
        dt_min = (now_ts - ev.timestamp) / 60000.0

        # current CI
        ci = carb_impact(dt_min, cat_hours)
        total_ci += ci * ev.carbs

        # remaining carbs
        if dt_min < cat_hours * 60:
            total_cob += ev.carbs * (1 - dt_min / (cat_hours * 60))

        # predicted CI for next 48 steps
        for i in range(48):
            future_t = dt_min + i * 5
            predcis[i] += carb_impact(future_t, cat_hours) * ev.carbs

    return total_cob, total_ci, predcis
