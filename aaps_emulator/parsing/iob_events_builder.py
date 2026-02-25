from aaps_emulator.core.iob import InsulinEvent


def build_iob_events(rt_dict):
    """
    Build insulin events from normalized RT.
    Supports:
      - bolus (units)
      - temp basal (rate + duration)
    """

    events = []
    if not isinstance(rt_dict, dict):
        return events

    ts = rt_dict.get("timestamp")
    if not ts:
        return events

    # bolus
    units = rt_dict.get("units")
    if units:
        events.append(InsulinEvent(timestamp=int(ts), amount=float(units), duration=0, rate=0, type="bolus"))

    # temp basal
    rate = rt_dict.get("rate")
    duration = rt_dict.get("duration")
    if rate is not None and duration is not None:
        events.append(InsulinEvent(timestamp=int(ts), amount=0, duration=int(duration), rate=float(rate), type="temp"))

    return events
