from __future__ import annotations

from aaps_emulator.core.autoisf_structs import OapsProfileAutoIsf
from aaps_emulator.parsing.context_parsers import (
    parse_autosens,
    parse_current_temp,
    parse_glucose_status,
    parse_iob_history,
    parse_meal,
    parse_profile,
)
from aaps_emulator.parsing.rt_parser import normalize_rt


def build_inputs(block):
    ctx = block["context"]
    rt = normalize_rt(block["rt"])

    gs = parse_glucose_status(ctx)
    temp = parse_current_temp(ctx)
    iob_hist = parse_iob_history(ctx)
    prof = parse_profile(ctx)
    autosens = parse_autosens(ctx)
    meal = parse_meal(ctx)

    if not gs:
        return None

    # rt is normalized: variable_sens (if present) is numeric and already in expected units
    if prof and (getattr(prof, "variable_sens", None) is None or getattr(prof, "variable_sens", 0) == 0):
        if rt.get("variable_sens") is not None:
            prof.variable_sens = float(rt["variable_sens"])

    # use normalized target_bg (mmol/L) if present, else default 100 mg/dL -> 100/18 mmol/L
    target_bg_rt = rt.get("target_bg")
    if target_bg_rt is None:
        target_bg_rt = 100.0 / 18.0

    if prof:
        prof.target_bg = float(target_bg_rt)
    else:
        prof = OapsProfileAutoIsf(
            min_bg=4.0,
            max_bg=8.0,
            target_bg=float(target_bg_rt),
            sens=6.0,
            carb_ratio=15,
            current_basal=0.5,
            max_basal=2.0,
            max_daily_basal=2.0,
            max_iob=10,
            autosens_max=1.2,
            sensitivity_raises_target=False,
            resistance_lowers_target=False,
            adv_target_adjustments=False,
            enable_uam=True,
            exercise_mode=False,
            high_temptarget_raises_sensitivity=False,
            low_temptarget_lowers_sensitivity=False,
            half_basal_exercise_target=160,
            temptarget_set=False,
            remainingCarbsCap=90,
            maxSMBBasalMinutes=90,
            maxUAMSMBBasalMinutes=60,
            bolus_increment=0.1,
            skip_neutral_temps=False,
            enableSMB_always=True,
            enableSMB_with_COB=True,
            enableSMB_after_carbs=True,
            enableSMB_with_temptarget=True,
            allowSMB_with_high_temptarget=False,
            SMBInterval=5,
            smb_delivery_ratio=0.5,
            smb_delivery_ratio_min=0.5,
            smb_delivery_ratio_max=0.6,
            smb_delivery_ratio_bg_range=0.0,
            smb_max_range_extension=1.0,
            autoISF_version="3.0.1",
            variable_sens=6.0,
        )

    return {
        "glucose_status": gs,
        "current_temp": temp,
        "iob_array": iob_hist,
        "profile": prof,
        "autosens": autosens,
        "meal": meal,
        "rt": rt,
    }
