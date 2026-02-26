from __future__ import annotations

from aaps_emulator.core.cob import CarbEvent
from aaps_emulator.parsing.context_parsers import (
    parse_autosens,
    parse_current_temp,
    parse_glucose_status,
    parse_iob_history,
    parse_meal,
    parse_profile,
)
from aaps_emulator.parsing.iob_events_builder import build_iob_events
from aaps_emulator.parsing.rt_parser import normalize_rt


def build_inputs(block):
    ctx = block["context"]

    # RT RAW STRING
    rt_raw = block.get("rt")
    rt = normalize_rt(rt_raw)

    gs = parse_glucose_status(ctx)
    temp = parse_current_temp(ctx)
    iob_hist = parse_iob_history(ctx)
    prof = parse_profile(ctx)
    autosens = parse_autosens(ctx)
    meal = parse_meal(ctx)

    # Build carb events
    cob_events = []
    if meal and meal.carbs > 0:
        cob_events.append(CarbEvent(timestamp=int(meal.last_carb_time), carbs=float(meal.carbs), absorption=2.0))

    if not gs:
        return None

    # variable_sens from RT
    if prof and (not getattr(prof, "variable_sens", None)) and rt.get("variable_sens") is not None:
        prof.variable_sens = float(rt["variable_sens"])

    # target BG
    target_bg_rt = rt.get("target_bg")
    if target_bg_rt is None:
        target_bg_rt = 100.0 / 18.0

    if prof:
        prof.target_bg = float(target_bg_rt)

    return {
        "glucose_status": gs,
        "current_temp": temp,
        "iob_array": build_iob_events(rt),
        "iob_total": iob_hist,
        "profile": prof,
        "autosens": autosens,
        "meal": meal,
        "cob_events": cob_events,
        "rt": rt,
    }
