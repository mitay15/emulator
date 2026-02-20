import re
from core.autoisf_structs import (
    GlucoseStatus, IobTotal, MealData, AutosensResult,
    CurrentTemp, OapsProfileAutoIsf
)
from parsing.utils import clean_num


def parse_glucose_status(context):
    gs_line = None
    for line in context:
        if "GlucoseStatusAutoIsf" in line:
            gs_line = line
            break

    if not gs_line:
        return None

    gs_line = gs_line.replace(" ", "").replace("\t", "")

    def get(name):
        m = re.search(rf"{name}=([0-9.\-E]+)", gs_line)
        return clean_num(m.group(1).rstrip(",")) if m else None

    return GlucoseStatus(
        glucose=(get("glucose") or 0) / 18.0,
        delta=(get("delta") or 0) / 18.0,
        short_avg_delta=(get("shortAvgDelta") or 0) / 18.0,
        long_avg_delta=(get("longAvgDelta") or 0) / 18.0,
        date=int(get("date") or 0),
        noise=get("noise") or 0
    )


def parse_current_temp(context):
    for line in context:
        if "CurrentTemp(" in line:
            dur = re.search(r"duration=([0-9.\-]+)", line)
            rate = re.search(r"rate=([0-9.\-]+)", line)
            return CurrentTemp(
                duration=int(clean_num(dur.group(1))) if dur else 0,
                rate=clean_num(rate.group(1)) if rate else 0.0,
                minutes_running=0
            )
    return CurrentTemp(duration=0, rate=0.0, minutes_running=0)


def parse_iob_history(context):
    iobs = []
    for line in context:
        if "IobTotal(" in line:
            clean = line.replace(" ", "")
            m = re.search(
                r"IobTotal\(time=(\d+),iob=([0-9.\-E]+),activity=([0-9.\-E]+)",
                clean
            )
            if m:
                iobs.append(
                    IobTotal(
                        iob=clean_num(m.group(2)),
                        activity=clean_num(m.group(3)),
                        iob_with_zero_temp=None
                    )
                )
    return iobs


def parse_profile(context):
    prof_line = None
    for line in context:
        if "OapsProfileAutoIsf" in line:
            prof_line = line
            break

    if not prof_line:
        return None

    prof_line = prof_line.replace(" ", "").replace("\t", "")

    def get(name):
        m = re.search(rf"{name}=([0-9.\-E]+)", prof_line)
        return clean_num(m.group(1).rstrip(",")) if m else None

    variable_sens = get("variable_sens")
    if variable_sens is not None:
        variable_sens /= 18.0

    return OapsProfileAutoIsf(
        min_bg=(get("min_bg") or 80) / 18.0,
        max_bg=(get("max_bg") or 120) / 18.0,
        target_bg=(get("target_bg") or 100) / 18.0,
        sens=(get("sens") or 100) / 18.0,
        carb_ratio=get("carb_ratio") or 15,
        current_basal=get("current_basal") or 0.5,
        max_basal=get("max_basal") or 2.0,
        max_daily_basal=get("max_daily_basal") or 2.0,
        max_iob=get("max_iob") or 10,
        autosens_max=get("autosens_max") or 1.2,
        enable_uam="enableUAM=true" in prof_line,
        enableSMB_always="enableSMB_always=true" in prof_line,
        enableSMB_with_COB="enableSMB_with_COB=true" in prof_line,
        enableSMB_after_carbs="enableSMB_after_carbs=true" in prof_line,
        enableSMB_with_temptarget="enableSMB_with_temptarget=true" in prof_line,
        allowSMB_with_high_temptarget="allowSMB_with_high_temptarget=true" in prof_line,
        SMBInterval=get("SMBInterval") or 5,
        smb_delivery_ratio=get("smb_delivery_ratio") or 0.5,
        smb_delivery_ratio_min=get("smb_delivery_ratio_min") or 0.5,
        smb_delivery_ratio_max=get("smb_delivery_ratio_max") or 0.6,
        smb_delivery_ratio_bg_range=get("smb_delivery_ratio_bg_range") or 0.0,
        smb_max_range_extension=get("smb_max_range_extension") or 1.0,
        maxSMBBasalMinutes=get("maxSMBBasalMinutes") or 90,
        maxUAMSMBBasalMinutes=get("maxUAMSMBBasalMinutes") or 60,
        variable_sens=variable_sens
    )


def parse_autosens(context):
    for line in context:
        if "AutosensResult" in line:
            clean = line.replace(" ", "").replace("\t", "")
            m = re.search(r"ratio=([0-9.\-E]+)", clean)
            if m:
                return AutosensResult(
                    ratio=clean_num(m.group(1)),
                    sens_result=line
                )
    return AutosensResult(ratio=1.0, sens_result="none")


def parse_meal(context):
    meal_line = None
    for line in context:
        if "MealData(" in line:
            meal_line = line
            break

    if not meal_line:
        return MealData(0, 0, 0, 0.0, 0.0)

    meal_line = meal_line.replace(" ", "").replace("\t", "")

    def get(name):
        m = re.search(rf"{name}=([0-9.\-E]+)", meal_line)
        return clean_num(m.group(1).rstrip(",")) if m else None

    carbs = get("carbs") or 0
    meal_cob = get("mealCOB") or 0
    last = get("lastCarbTime") or 0

    if meal_cob == 0 and carbs > 0:
        meal_cob = carbs

    return MealData(
        carbs=carbs,
        meal_cob=meal_cob,
        last_carb_time=last,
        slope_from_max_deviation=0.0,
        slope_from_min_deviation=0.0
    )
