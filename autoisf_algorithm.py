from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

# ============================
# БАЗОВЫЕ СТРУКТУРЫ ДАННЫХ
# ============================


@dataclass
class GlucoseStatus:
    glucose: float  # BG in mmol/L
    delta: float  # 5m delta in mmol/L
    short_avg_delta: float  # 15m delta
    long_avg_delta: float  # 40m delta
    date: int  # timestamp (ms)
    noise: float  # CGM noise level


@dataclass
class IobTotal:
    iob: float  # insulin on board (U)
    activity: float  # insulin activity (U/min)
    iob_with_zero_temp: Optional["IobTotal"] = None


@dataclass
class MealData:
    carbs: float
    meal_cob: float
    last_carb_time: int
    slope_from_max_deviation: float
    slope_from_min_deviation: float


@dataclass
class AutosensResult:
    ratio: float = 1.0
    sens_result: str = ""


@dataclass
class CurrentTemp:
    duration: int  # minutes remaining
    rate: float  # U/hr
    minutes_running: int  # how long temp basal has been running


@dataclass
class Predictions:
    IOB: Optional[List[int]] = None
    COB: Optional[List[int]] = None
    aCOB: Optional[List[int]] = None
    UAM: Optional[List[int]] = None
    ZT: Optional[List[int]] = None


@dataclass
class OapsProfileAutoIsf:
    # BG targets (mmol/L)
    min_bg: float
    max_bg: float
    target_bg: float

    # insulin / carbs
    sens: float  # ISF (mmol/U)
    carb_ratio: float  # CR (g/U)
    current_basal: float  # U/hr
    max_basal: float  # U/hr
    max_daily_basal: float  # U/hr
    max_iob: float  # U

    # autosens
    autosens_max: float
    sensitivity_raises_target: bool
    resistance_lowers_target: bool
    adv_target_adjustments: bool

    # UAM / SMB / TT
    enable_uam: bool
    exercise_mode: bool
    high_temptarget_raises_sensitivity: bool
    low_temptarget_lowers_sensitivity: bool
    half_basal_exercise_target: int
    temptarget_set: bool

    # safety
    remainingCarbsCap: int
    maxSMBBasalMinutes: int
    maxUAMSMBBasalMinutes: int
    bolus_increment: float
    skip_neutral_temps: bool

    # SMB flags
    enableSMB_always: bool
    enableSMB_with_COB: bool
    enableSMB_after_carbs: bool
    enableSMB_with_temptarget: bool
    allowSMB_with_high_temptarget: bool

    # SMB config
    SMBInterval: int
    smb_delivery_ratio: float
    smb_delivery_ratio_min: float
    smb_delivery_ratio_max: float
    smb_delivery_ratio_bg_range: float
    smb_max_range_extension: float

    # misc
    autoISF_version: str
    variable_sens: float


@dataclass
class RT:
    algorithm: str
    running_dynamic_isf: bool
    timestamp: int

    bg: Optional[float] = None
    tick: Optional[str] = None
    eventualBG: Optional[float] = None
    targetBG: Optional[float] = None
    insulinReq: Optional[float] = None
    carbsReq: Optional[int] = None
    carbsReqWithin: Optional[int] = None

    deliverAt: Optional[int] = None
    sensitivityRatio: Optional[float] = None

    duration: Optional[int] = None
    rate: Optional[float] = None

    predBGs: Optional[Predictions] = None

    COB: Optional[float] = None
    IOB: Optional[float] = None
    variable_sens: Optional[float] = None

    reason: str = ""
    consoleLog: List[str] = field(default_factory=list)
    consoleError: List[str] = field(default_factory=list)


# ============================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================


def round_dec(value: float, digits: int) -> float:
    if math.isnan(value):
        return float("nan")
    scale = 10.0**digits
    return round(value * scale) / scale


def to_fixed2(value: float) -> str:
    return f"{round_dec(value, 2):.2f}".replace(".", ",")


def without_zeros(value: float) -> str:
    s = f"{value:.2f}"
    s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def convert_bg(value: float) -> str:
    # уже в mmol/L, просто форматируем
    return f"{round_dec(value, 1):.1f}".replace(".", ",")


def calculate_expected_delta(target_bg: float, eventual_bg: float, bgi: float) -> float:
    five_min_blocks = (2 * 60) / 5
    target_delta = target_bg - eventual_bg
    return round_dec(bgi + (target_delta / five_min_blocks), 1)


def get_max_safe_basal(profile: OapsProfileAutoIsf) -> float:
    return min(
        profile.max_basal,
        min(
            profile.max_daily_basal * profile.autosens_max,
            profile.current_basal * profile.autosens_max * 2,
        ),
    )


def set_temp_basal(
    rate: float,
    duration: int,
    profile: OapsProfileAutoIsf,
    rT: RT,
    currenttemp: CurrentTemp,
) -> RT:
    max_safe_basal = min(
        profile.max_basal,
        min(
            profile.max_daily_basal * profile.autosens_max,
            profile.current_basal * profile.autosens_max * 2,
        ),
    )
    if rate < 0:
        rate = 0.0
    elif rate > max_safe_basal:
        rate = max_safe_basal

    suggested_rate = rate

    if (
        currenttemp.duration > (duration - 10)
        and currenttemp.duration <= 120
        and suggested_rate <= currenttemp.rate * 1.2
        and suggested_rate >= currenttemp.rate * 0.8
        and duration > 0
    ):
        rT.reason += f" {currenttemp.duration}m left and {without_zeros(currenttemp.rate)} ~ req {without_zeros(suggested_rate)}U/hr: no temp required"
        return rT

    if abs(suggested_rate - profile.current_basal) < 1e-9:
        if profile.skip_neutral_temps:
            if currenttemp.duration > 0:
                rT.reason += " Suggested rate is same as profile rate, a temp basal is active, canceling current temp"
                rT.duration = 0
                rT.rate = 0.0
                return rT
            else:
                rT.reason += " Suggested rate is same as profile rate, no temp basal is active, doing nothing"
                return rT
        else:
            rT.reason += f" Setting neutral temp basal of {profile.current_basal}U/hr"
            rT.duration = duration
            rT.rate = suggested_rate
            return rT
    else:
        rT.duration = duration
        rT.rate = suggested_rate
        return rT


def enable_smb(
    profile: OapsProfileAutoIsf,
    microbolus_allowed: bool,
    meal: MealData,
    target_bg: float,
    console: List[str],
) -> bool:
    if not microbolus_allowed:
        console.append("SMB disabled (!microBolusAllowed)")
        return False
    elif (
        not profile.allowSMB_with_high_temptarget
        and profile.temptarget_set
        and target_bg > 5.5
    ):  # 100 mg/dL
        console.append(f"SMB disabled due to high temptarget of {target_bg}")
        return False

    if profile.enableSMB_always:
        console.append("SMB enabled due to enableSMB_always")
        return True

    if profile.enableSMB_with_COB and meal.meal_cob != 0:
        console.append(f"SMB enabled for COB of {meal.meal_cob}")
        return True

    if profile.enableSMB_after_carbs and meal.carbs != 0:
        console.append("SMB enabled for 6h after carb entry")
        return True

    if profile.enableSMB_with_temptarget and profile.temptarget_set and target_bg < 5.5:
        console.append(f"SMB enabled for temptarget of {convert_bg(target_bg)}")
        return True

    console.append(
        "SMB disabled (no enableSMB preferences active or no condition satisfied)"
    )
    return False


# ============================
# ОСНОВНОЙ АЛГОРИТМ AUTOISF
# ============================


def determine_basal_autoisf(
    glucose_status: GlucoseStatus,
    currenttemp: CurrentTemp,
    iob_data_array: List[IobTotal],
    profile: OapsProfileAutoIsf,
    autosens_data: AutosensResult,
    meal_data: MealData,
    microBolusAllowed: bool,
    currentTime: int,
    flatBGsDetected: bool,
    autoIsfMode: bool,
    loop_wanted_smb: str,
    profile_percentage: int,
    smb_ratio: float,
    smb_max_range_extension: float,
    iob_threshold_percent: int,
    auto_isf_consoleError: List[str],
    auto_isf_consoleLog: List[str],
) -> RT:

    consoleError: List[str] = []
    consoleLog: List[str] = []

    rT = RT(
        algorithm="AUTO_ISF",
        running_dynamic_isf=autoIsfMode,
        timestamp=currentTime,
        consoleLog=consoleLog,
        consoleError=consoleError,
    )

    deliverAt = currentTime
    profile_current_basal = profile.current_basal
    basal = profile_current_basal

    systemTime = currentTime
    bgTime = glucose_status.date
    minAgo = round_dec((systemTime - bgTime) / 60_000.0, 1)
    bg = glucose_status.glucose
    noise = glucose_status.noise

    if bg <= 0.6 or noise >= 3:  # ~10 mg/dL
        rT.reason += "CGM is calibrating, in ??? state, or noise is high"
    if minAgo > 12 or minAgo < -5:
        rT.reason += f"If current system time {systemTime} is correct, then BG data is too old. The last BG data was read {minAgo}m ago at {bgTime}"
    elif bg > 3.3 and flatBGsDetected:  # >60 mg/dL
        rT.reason += "Error: CGM data is unchanged for the past ~45m"

    if (
        bg <= 0.6
        or noise >= 3
        or minAgo > 12
        or minAgo < -5
        or (bg > 3.3 and flatBGsDetected)
    ):
        if currenttemp.rate > basal:
            rT.reason += f". Replacing high temp basal of {currenttemp.rate} with neutral temp of {basal}"
            rT.deliverAt = deliverAt
            rT.duration = 30
            rT.rate = basal
            return rT
        elif currenttemp.rate == 0.0 and currenttemp.duration > 30:
            rT.reason += f". Shortening {currenttemp.duration}m long zero temp to 30m. "
            rT.deliverAt = deliverAt
            rT.duration = 30
            rT.rate = 0.0
            return rT
        else:
            rT.reason += f". Temp {currenttemp.rate} <= current basal {round_dec(basal, 2)}U/hr; doing nothing. "
            return rT

    max_iob = profile.max_iob

    target_bg = (profile.min_bg + profile.max_bg) / 2
    min_bg = profile.min_bg
    max_bg = profile.max_bg

    sensitivityRatio = 1.0
    exercise_ratio = 1.0
    high_temptarget_raises_sensitivity = (
        profile.exercise_mode or profile.high_temptarget_raises_sensitivity
    )
    normalTarget = 5.5  # 100 mg/dL
    halfBasalTarget = profile.half_basal_exercise_target / 18.0  # mg/dL→mmol

    if (
        high_temptarget_raises_sensitivity
        and profile.temptarget_set
        and target_bg > normalTarget
    ) or (
        profile.low_temptarget_lowers_sensitivity
        and profile.temptarget_set
        and target_bg < normalTarget
    ):
        c = halfBasalTarget - normalTarget
        if c * (c + target_bg - normalTarget) <= 0:
            sensitivityRatio = profile.autosens_max
        else:
            sensitivityRatio = c / (c + target_bg - normalTarget)
            sensitivityRatio = min(sensitivityRatio, profile.autosens_max)
            sensitivityRatio = round_dec(sensitivityRatio, 2)
            exercise_ratio = sensitivityRatio
            consoleError.append(
                f"Sensitivity ratio set to {sensitivityRatio} based on temp target of {target_bg}; "
            )
    else:
        sensitivityRatio = autosens_data.ratio
        consoleError.append(f"Autosens ratio: {sensitivityRatio}; ")

    iobTH_reduction_ratio = 1.0
    if iob_threshold_percent != 100:
        iobTH_reduction_ratio = profile_percentage / 100.0 * exercise_ratio

    basal = profile.current_basal * sensitivityRatio
    basal = basal
    if abs(basal - profile_current_basal) > 1e-9:
        consoleError.append(f"Adjusting basal from {profile_current_basal} to {basal};")
    else:
        consoleError.append(f"Basal unchanged: {basal};")

    if not profile.temptarget_set:
        if (profile.sensitivity_raises_target and autosens_data.ratio < 1) or (
            profile.resistance_lowers_target and autosens_data.ratio > 1
        ):
            min_bg = round_dec((min_bg - 3.3) / autosens_data.ratio, 1) + 3.3
            max_bg = round_dec((max_bg - 3.3) / autosens_data.ratio, 1) + 3.3
            new_target_bg = round_dec((target_bg - 3.3) / autosens_data.ratio, 1) + 3.3
            new_target_bg = max(4.4, new_target_bg)
            if abs(target_bg - new_target_bg) < 1e-9:
                consoleError.append(f"target_bg unchanged: {new_target_bg}; ")
            else:
                consoleError.append(f"target_bg from {target_bg} to {new_target_bg}; ")
            target_bg = new_target_bg

    iobArray = iob_data_array
    iob_data = iobArray[0]

    if glucose_status.delta > -0.05:
        tick = f"+{round(iob_data_array[0].iob)}"
    else:
        tick = str(round(glucose_status.delta))

    minDelta = min(glucose_status.delta, glucose_status.short_avg_delta)
    minAvgDelta = min(glucose_status.short_avg_delta, glucose_status.long_avg_delta)
    maxDelta = max(
        glucose_status.delta,
        max(glucose_status.short_avg_delta, glucose_status.long_avg_delta),
    )

    profile_sens = round_dec(profile.sens, 1)
    adjusted_sens = round_dec(profile.sens / sensitivityRatio, 1)
    if abs(adjusted_sens - profile_sens) > 1e-9:
        consoleError.append(f"ISF from {profile_sens} to {adjusted_sens}")
    else:
        consoleError.append(f"ISF unchanged: {adjusted_sens}")
    if autoIsfMode:
        sens = profile.variable_sens
    else:
        sens = adjusted_sens
    consoleError.append(f"CR: {profile.carb_ratio}")

    if autoIsfMode:
        consoleError.append("----------------------------------")
        consoleError.append(f"start AutoISF {profile.autoISF_version}")
        consoleError.append("----------------------------------")
        consoleError.extend(auto_isf_consoleLog)
        consoleError.extend(auto_isf_consoleError)

    iobTHtolerance = 130.0
    iobTHvirtual = (
        iob_threshold_percent
        * iobTHtolerance
        / 10000.0
        * profile.max_iob
        * iobTH_reduction_ratio
    )

    enableSMB = False
    if microBolusAllowed and loop_wanted_smb != "AAPS":
        if loop_wanted_smb in ("enforced", "fullLoop"):
            enableSMB = True
    else:
        enableSMB = enable_smb(
            profile, microBolusAllowed, meal_data, target_bg, consoleError
        )

    bgi = round_dec(-iob_data.activity * sens * 5, 2)

    deviation = round_dec(30 / 5 * (minDelta - bgi), 0)
    if deviation < 0:
        deviation = round_dec(30 / 5 * (minAvgDelta - bgi), 0)
        if deviation < 0:
            deviation = round_dec(30 / 5 * (glucose_status.long_avg_delta - bgi), 0)

    if autoIsfMode:
        naive_eventualBG = round_dec(bg - (iob_data.iob * sens), 1)
    else:
        if iob_data.iob > 0:
            naive_eventualBG = round_dec(bg - (iob_data.iob * sens), 1)
        else:
            naive_eventualBG = round_dec(
                bg - (iob_data.iob * min(sens, profile.sens)), 1
            )

    eventualBG = naive_eventualBG + deviation

    if bg > max_bg and profile.adv_target_adjustments and not profile.temptarget_set:
        adjustedMinBG = round_dec(max(4.4, min_bg - (bg - min_bg) / 3.0), 1)
        adjustedTargetBG = round_dec(max(4.4, target_bg - (bg - target_bg) / 3.0), 1)
        adjustedMaxBG = round_dec(max(4.4, max_bg - (bg - max_bg) / 3.0), 1)

        if (
            eventualBG > adjustedMinBG
            and naive_eventualBG > adjustedMinBG
            and min_bg > adjustedMinBG
        ):
            consoleError.append(
                f"Adjusting targets for high BG: min_bg from {min_bg} to {adjustedMinBG}; "
            )
            min_bg = adjustedMinBG
        else:
            consoleError.append(f"min_bg unchanged: {min_bg}; ")

        if (
            eventualBG > adjustedTargetBG
            and naive_eventualBG > adjustedTargetBG
            and target_bg > adjustedTargetBG
        ):
            consoleError.append(f"target_bg from {target_bg} to {adjustedTargetBG}; ")
            target_bg = adjustedTargetBG
        else:
            consoleError.append(f"target_bg unchanged: {target_bg}; ")

        if (
            eventualBG > adjustedMaxBG
            and naive_eventualBG > adjustedMaxBG
            and max_bg > adjustedMaxBG
        ):
            consoleError.append(f"max_bg from {max_bg} to {adjustedMaxBG}")
            max_bg = adjustedMaxBG
        else:
            consoleError.append(f"max_bg unchanged: {max_bg}")

    expectedDelta = calculate_expected_delta(target_bg, eventualBG, bgi)

    threshold = min_bg - 0.5 * (min_bg - 2.2)  # 40 mg/dL → 2.2 mmol

    rT = RT(
        algorithm="AUTO_ISF",
        running_dynamic_isf=autoIsfMode,
        timestamp=currentTime,
        bg=bg,
        tick=tick,
        eventualBG=eventualBG,
        targetBG=target_bg,
        insulinReq=0.0,
        deliverAt=deliverAt,
        sensitivityRatio=sensitivityRatio,
        consoleLog=consoleLog,
        consoleError=consoleError,
        variable_sens=profile.variable_sens,
    )

    COBpredBGs: List[float] = [bg]
    aCOBpredBGs: List[float] = [bg]
    IOBpredBGs: List[float] = [bg]
    UAMpredBGs: List[float] = [bg]
    ZTpredBGs: List[float] = [bg]

    enableUAM = profile.enable_uam

    ci = round_dec((minDelta - bgi), 1)
    uci = round_dec((minDelta - bgi), 1)

    csf = sens / profile.carb_ratio
    consoleError.append(f"profile.sens: {profile.sens}, sens: {sens}, CSF: {csf}")

    maxCarbAbsorptionRate = 30
    maxCI = round_dec(maxCarbAbsorptionRate * csf * 5 / 60, 1)
    if ci > maxCI:
        consoleError.append(
            f"Limiting carb impact from {ci} to {maxCI} mmol/L per 5m ( {maxCarbAbsorptionRate} g/h )"
        )
        ci = maxCI

    remainingCATimeMin = 3.0
    remainingCATimeMin = remainingCATimeMin / sensitivityRatio
    assumedCarbAbsorptionRate = 20
    remainingCATime = remainingCATimeMin

    if meal_data.carbs != 0:
        remainingCATimeMin = max(
            remainingCATimeMin, meal_data.meal_cob / assumedCarbAbsorptionRate
        )
        lastCarbAge = round_dec((systemTime - meal_data.last_carb_time) / 60000.0, 0)
        fractionCOBAbsorbed = (meal_data.carbs - meal_data.meal_cob) / meal_data.carbs
        remainingCATime = remainingCATimeMin + 1.5 * lastCarbAge / 60
        remainingCATime = round_dec(remainingCATime, 1)
        consoleError.append(
            f"Last carbs {lastCarbAge}minutes ago; remainingCATime:{remainingCATime}hours;{round_dec(fractionCOBAbsorbed * 100, 0)}% carbs absorbed"
        )

    totalCI = max(0.0, ci / 5 * 60 * remainingCATime / 2)
    totalCA = totalCI / csf
    remainingCarbsCap = min(90, profile.remainingCarbsCap)
    remainingCarbs = max(0.0, meal_data.meal_cob - totalCA)
    remainingCarbs = min(remainingCarbsCap, remainingCarbs)
    remainingCIpeak = remainingCarbs * csf * 5 / 60 / (remainingCATime / 2)

    slopeFromMaxDeviation = round_dec(meal_data.slope_from_max_deviation, 2)
    slopeFromMinDeviation = round_dec(meal_data.slope_from_min_deviation, 2)
    slopeFromDeviations = min(slopeFromMaxDeviation, -slopeFromMinDeviation / 3)

    aci = 10
    if ci == 0:
        cid = 0.0
    else:
        cid = min(remainingCATime * 60 / 5 / 2, max(0.0, meal_data.meal_cob * csf / ci))
    acid = max(0.0, meal_data.meal_cob * csf / aci)

    consoleError.append(
        f"Carb Impact: {ci} mmol/L per 5m; CI Duration: {round_dec(cid * 5 / 60 * 2, 1)} hours; remaining CI (~2h peak): {round_dec(remainingCIpeak, 1)} mmol/L per 5m"
    )

    minIOBPredBG = 999.0
    minCOBPredBG = 999.0
    minUAMPredBG = 999.0
    minCOBGuardBG = 999.0
    minUAMGuardBG = 999.0
    minIOBGuardBG = 999.0
    minZTGuardBG = 999.0

    UAMduration = 0.0
    remainingCItotal = 0.0
    remainingCIs: List[int] = []
    predCIs: List[int] = []
    UAMpredBG: Optional[float] = None
    COBpredBG: Optional[float] = None
    aCOBpredBG: Optional[float] = None

    for iobTick in iobArray:
        predBGI = round_dec(-iobTick.activity * sens * 5, 2)
        IOBpredBGI = predBGI
        if iobTick.iob_with_zero_temp is None:
            predZTBGI = predBGI
        else:
            predZTBGI = round_dec(-iobTick.iob_with_zero_temp.activity * sens * 5, 2)
        predUAMBGI = predBGI

        predDev = ci * (1 - min(1.0, len(IOBpredBGs) / (60.0 / 5.0)))
        IOBpredBG = IOBpredBGs[-1] + IOBpredBGI + predDev
        ZTpredBG = ZTpredBGs[-1] + predZTBGI

        predCI = max(0.0, max(0.0, ci) * (1 - len(COBpredBGs) / max(cid * 2, 1.0)))
        predACI = max(0.0, max(0, aci) * (1 - len(COBpredBGs) / max(acid * 2, 1.0)))

        intervals = min(len(COBpredBGs), (remainingCATime * 12) - len(COBpredBGs))
        remainingCI = max(0.0, intervals / (remainingCATime / 2 * 12) * remainingCIpeak)
        remainingCItotal += predCI + remainingCI
        remainingCIs.append(round(predCI + remainingCI))
        predCIs.append(round(predCI))

        COBpredBG = COBpredBGs[-1] + predBGI + min(0.0, predDev) + predCI + remainingCI
        aCOBpredBG = aCOBpredBGs[-1] + predBGI + min(0.0, predDev) + predACI

        predUCIslope = max(0.0, uci + (len(UAMpredBGs) * slopeFromDeviations))
        predUCImax = max(0.0, uci * (1 - len(UAMpredBGs) / max(3.0 * 60 / 5, 1.0)))
        predUCI = min(predUCIslope, predUCImax)
        if predUCI > 0:
            UAMduration = round_dec((len(UAMpredBGs) + 1) * 5 / 60.0, 1)
        UAMpredBG = UAMpredBGs[-1] + predUAMBGI + min(0.0, predDev) + predUCI

        if len(IOBpredBGs) < 48:
            IOBpredBGs.append(IOBpredBG)
        if len(COBpredBGs) < 48:
            COBpredBGs.append(COBpredBG)
        if len(aCOBpredBGs) < 48:
            aCOBpredBGs.append(aCOBpredBG)
        if len(UAMpredBGs) < 48:
            UAMpredBGs.append(UAMpredBG)
        if len(ZTpredBGs) < 48:
            ZTpredBGs.append(ZTpredBG)

        if COBpredBG < minCOBGuardBG:
            minCOBGuardBG = round_dec(COBpredBG, 0)
        if UAMpredBG < minUAMGuardBG:
            minUAMGuardBG = round_dec(UAMpredBG, 0)
        if IOBpredBG < minIOBGuardBG:
            minIOBGuardBG = IOBpredBG
        if ZTpredBG < minZTGuardBG:
            minZTGuardBG = round_dec(ZTpredBG, 0)

        insulinPeakTime = 90
        insulinPeak5m = (insulinPeakTime / 60.0) * 12.0

        if len(IOBpredBGs) > insulinPeak5m and IOBpredBG < minIOBPredBG:
            minIOBPredBG = round_dec(IOBpredBG, 0)
        if IOBpredBG > bg:
            pass

        if (
            (cid != 0.0 or remainingCIpeak > 0)
            and len(COBpredBGs) > insulinPeak5m
            and COBpredBG < minCOBPredBG
        ):
            minCOBPredBG = round_dec(COBpredBG, 0)
        if enableUAM and len(UAMpredBGs) > 12 and UAMpredBG < minUAMPredBG:
            minUAMPredBG = round_dec(UAMpredBG, 0)

    if meal_data.meal_cob > 0:
        consoleError.append("predCIs (mmol/L/5m):" + " ".join(str(x) for x in predCIs))
        consoleError.append(
            "remainingCIs:      " + " ".join(str(x) for x in remainingCIs)
        )

    rT.predBGs = Predictions()

    IOBpredBGs = [round_dec(min(22.3, max(2.2, x)), 1) for x in IOBpredBGs]
    for i in range(len(IOBpredBGs) - 1, 12, -1):
        if IOBpredBGs[i - 1] != IOBpredBGs[i]:
            break
        else:
            IOBpredBGs.pop()
    rT.predBGs.IOB = [
        int(round(x * 18)) for x in IOBpredBGs
    ]  # если хочешь хранить в mg/dL — убери

    lastIOBpredBG = IOBpredBGs[-1]

    ZTpredBGs = [round_dec(min(22.3, max(2.2, x)), 1) for x in ZTpredBGs]
    for i in range(len(ZTpredBGs) - 1, 6, -1):
        if ZTpredBGs[i - 1] >= ZTpredBGs[i] or ZTpredBGs[i] <= target_bg:
            break
        else:
            ZTpredBGs.pop()
    rT.predBGs.ZT = [int(round(x * 18)) for x in ZTpredBGs]

    lastCOBpredBG = None
    lastUAMpredBG = None

    if meal_data.meal_cob > 0:
        aCOBpredBGs = [round_dec(min(22.3, max(2.2, x)), 1) for x in aCOBpredBGs]
        for i in range(len(aCOBpredBGs) - 1, 12, -1):
            if aCOBpredBGs[i - 1] != aCOBpredBGs[i]:
                break
            else:
                aCOBpredBGs.pop()

    if meal_data.meal_cob > 0 and (ci > 0 or remainingCIpeak > 0):
        COBpredBGs = [round_dec(min(22.3, max(2.2, x)), 1) for x in COBpredBGs]
        for i in range(len(COBpredBGs) - 1, 12, -1):
            if COBpredBGs[i - 1] != COBpredBGs[i]:
                break
            else:
                COBpredBGs.pop()
        rT.predBGs.COB = [int(round(x * 18)) for x in COBpredBGs]
        lastCOBpredBG = COBpredBGs[-1]
        eventualBG = max(eventualBG, round_dec(COBpredBGs[-1], 1))

    if ci > 0 or remainingCIpeak > 0:
        if enableUAM:
            UAMpredBGs = [round_dec(min(22.3, max(2.2, x)), 1) for x in UAMpredBGs]
            for i in range(len(UAMpredBGs) - 1, 12, -1):
                if UAMpredBGs[i - 1] != UAMpredBGs[i]:
                    break
                else:
                    UAMpredBGs.pop()
            rT.predBGs.UAM = [int(round(x * 18)) for x in UAMpredBGs]
            lastUAMpredBG = UAMpredBGs[-1]
            eventualBG = max(eventualBG, round_dec(UAMpredBGs[-1], 1))
        rT.eventualBG = eventualBG

    consoleError.append(
        f"UAM Impact: {uci} mmol/L per 5m; UAM Duration: {UAMduration} hours"
    )
    consoleError.append(f"EventualBG is {eventualBG} ;")

    minIOBPredBG = max(2.2, minIOBPredBG)
    minCOBPredBG = max(2.2, minCOBPredBG)
    minUAMPredBG = max(2.2, minUAMPredBG)
    minPredBG = round_dec(minIOBPredBG, 1)

    fractionCarbsLeft = (
        meal_data.meal_cob / meal_data.carbs if meal_data.carbs != 0 else 0
    )

    if minUAMPredBG < 999 and minCOBPredBG < 999:
        avgPredBG = round_dec(
            (1 - fractionCarbsLeft) * (lastUAMpredBG or minUAMPredBG)
            + fractionCarbsLeft * (lastCOBpredBG or minCOBPredBG),
            1,
        )
    elif minCOBPredBG < 999:
        avgPredBG = round_dec(
            (IOBpredBGs[-1] + (lastCOBpredBG or minCOBPredBG)) / 2.0, 1
        )
    elif minUAMPredBG < 999:
        avgPredBG = round_dec(
            (IOBpredBGs[-1] + (lastUAMpredBG or minUAMPredBG)) / 2.0, 1
        )
    else:
        avgPredBG = round_dec(IOBpredBGs[-1], 1)

    if minZTGuardBG > avgPredBG:
        avgPredBG = minZTGuardBG

    if cid > 0 or remainingCIpeak > 0:
        if enableUAM:
            minGuardBG = (
                fractionCarbsLeft * minCOBGuardBG
                + (1 - fractionCarbsLeft) * minUAMGuardBG
            )
        else:
            minGuardBG = minCOBGuardBG
    elif enableUAM:
        minGuardBG = minUAMGuardBG
    else:
        minGuardBG = minIOBGuardBG
    minGuardBG = round_dec(minGuardBG, 1)

    minZTUAMPredBG = minUAMPredBG
    if minZTGuardBG < threshold:
        minZTUAMPredBG = (minUAMPredBG + minZTGuardBG) / 2.0
    elif minZTGuardBG < target_bg:
        blendPct = (minZTGuardBG - threshold) / (target_bg - threshold)
        blendedMinZTGuardBG = minUAMPredBG * blendPct + minZTGuardBG * (1 - blendPct)
        minZTUAMPredBG = (minUAMPredBG + blendedMinZTGuardBG) / 2.0
    elif minZTGuardBG > minUAMPredBG:
        minZTUAMPredBG = (minUAMPredBG + minZTGuardBG) / 2.0
    minZTUAMPredBG = round_dec(minZTUAMPredBG, 1)

    if meal_data.carbs != 0:
        if not enableUAM and minCOBPredBG < 999:
            minPredBG = round_dec(max(minIOBPredBG, minCOBPredBG), 1)
        elif minCOBPredBG < 999:
            blendedMinPredBG = (
                fractionCarbsLeft * minCOBPredBG
                + (1 - fractionCarbsLeft) * minZTUAMPredBG
            )
            minPredBG = round_dec(
                max(minIOBPredBG, max(minCOBPredBG, blendedMinPredBG)), 1
            )
        elif enableUAM:
            minPredBG = minZTUAMPredBG
        else:
            minPredBG = minGuardBG
    elif enableUAM:
        minPredBG = round_dec(max(minIOBPredBG, minZTUAMPredBG), 1)

    minPredBG = min(minPredBG, avgPredBG)

    consoleError.append(
        f"minPredBG: {minPredBG} minIOBPredBG: {minIOBPredBG} minZTGuardBG: {minZTGuardBG}"
    )
    if minCOBPredBG < 999:
        consoleError.append(f" minCOBPredBG: {minCOBPredBG}")
    if minUAMPredBG < 999:
        consoleError.append(f" minUAMPredBG: {minUAMPredBG}")
    consoleError.append(
        f" avgPredBG: {avgPredBG} COB: {meal_data.meal_cob} / {meal_data.carbs}"
    )

    # ensure maxCOBPredBG exists
    maxCOBPredBG = locals().get("maxCOBPredBG", None)

    if maxCOBGuardBG := maxCOBPredBG if maxCOBPredBG is not None else bg:
        if maxCOBGuardBG > bg:
            minPredBG = min(minPredBG, maxCOBGuardBG)

    rT.COB = meal_data.meal_cob
    rT.IOB = iob_data.iob
    rT.reason += (
        f"COB: {without_zeros(round_dec(meal_data.meal_cob, 1))}, Dev: {convert_bg(deviation)}, "
        f"BGI: {convert_bg(bgi)}, ISF: {convert_bg(sens)}, CR: {without_zeros(round_dec(profile.carb_ratio, 2))}, "
        f"Target: {convert_bg(target_bg)}, minPredBG {convert_bg(minPredBG)}, "
        f"minGuardBG {convert_bg(minGuardBG)}, IOBpredBG {convert_bg(lastIOBpredBG)}"
    )
    if lastCOBpredBG is not None:
        rT.reason += f", COBpredBG {convert_bg(lastCOBpredBG)}"
    if lastUAMpredBG is not None:
        rT.reason += f", UAMpredBG {convert_bg(lastUAMpredBG)}"
    rT.reason += "; "

    carbsReqBG = naive_eventualBG
    if carbsReqBG < 2.2:
        carbsReqBG = min(minGuardBG, carbsReqBG)
    bgUndershoot = threshold - carbsReqBG

    minutesAboveMinBG = 240
    minutesAboveThreshold = 240
    if meal_data.meal_cob > 0 and (ci > 0 or remainingCIpeak > 0):
        for i, v in enumerate(COBpredBGs):
            if v < min_bg:
                minutesAboveMinBG = 5 * i
                break
        for i, v in enumerate(COBpredBGs):
            if v < threshold:
                minutesAboveThreshold = 5 * i
                break
    else:
        for i, v in enumerate(IOBpredBGs):
            if v < min_bg:
                minutesAboveMinBG = 5 * i
                break
        for i, v in enumerate(IOBpredBGs):
            if v < threshold:
                minutesAboveThreshold = 5 * i
                break

    if enableSMB and minGuardBG < threshold:
        consoleError.append(
            f"minGuardBG {convert_bg(minGuardBG)} projected below {convert_bg(threshold)} - disabling SMB"
        )
        enableSMB = False

    maxDeltaPercentage = 0.2
    if loop_wanted_smb == "fullLoop":
        maxDeltaPercentage = 0.3
    if maxDelta > maxDeltaPercentage * bg:
        consoleError.append(
            f"maxDelta {convert_bg(maxDelta)} > {100 * maxDeltaPercentage}% of BG {convert_bg(bg)} - disabling SMB"
        )
        rT.reason += f"maxDelta {convert_bg(maxDelta)} > {100 * maxDeltaPercentage}% of BG {convert_bg(bg)}: SMB disabled; "
        enableSMB = False

    consoleError.append(
        f"BG projected to remain above {convert_bg(min_bg)} for {minutesAboveMinBG} minutes"
    )
    if minutesAboveThreshold < 240 or minutesAboveMinBG < 60:
        consoleError.append(
            f"BG projected to remain above {convert_bg(threshold)} for {minutesAboveThreshold} minutes"
        )

    zeroTempDuration = minutesAboveThreshold
    zeroTempEffectDouble = profile.current_basal * sens * zeroTempDuration / 60
    COBforCarbsReq = max(0.0, meal_data.meal_cob - 0.25 * meal_data.carbs)
    carbsReq = round((bgUndershoot - zeroTempEffectDouble) / csf - COBforCarbsReq)
    zeroTempEffect = round(zeroTempEffectDouble)
    consoleError.append(
        f"naive_eventualBG: {naive_eventualBG} bgUndershoot: {bgUndershoot} zeroTempDuration {zeroTempDuration} zeroTempEffect: {zeroTempEffect} carbsReq: {carbsReq}"
    )
    if carbsReq >= profile.remainingCarbsCap and minutesAboveThreshold <= 45:
        rT.carbsReq = carbsReq
        rT.carbsReqWithin = minutesAboveThreshold
        rT.reason += f"{carbsReq} add'l carbs req w/in {minutesAboveThreshold}m; "

    if (
        bg < threshold
        and iob_data.iob < -profile.current_basal * 20 / 60
        and minDelta > 0
        and minDelta > expectedDelta
    ):
        rT.reason += (
            f"IOB {iob_data.iob} < {round_dec(-profile.current_basal * 20 / 60, 2)}"
        )
        rT.reason += f" and minDelta {convert_bg(minDelta)} > expectedDelta {convert_bg(expectedDelta)}; "
    elif bg < threshold or minGuardBG < threshold:
        rT.reason += f"minGuardBG {convert_bg(minGuardBG)} < {convert_bg(threshold)}"
        bgUndershoot = target_bg - minGuardBG
        worstCaseInsulinReq = bgUndershoot / sens
        durationReq = round(60 * worstCaseInsulinReq / profile.current_basal)
        durationReq = round(durationReq / 30) * 30
        durationReq = min(120, max(30, durationReq))
        return set_temp_basal(0.0, durationReq, profile, rT, currenttemp)

    deliver_at = rT.deliverAt

    if deliver_at is None:
        # fallback: используем текущее время
        deliver_at = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

    minutes = datetime.fromtimestamp(deliver_at / 1000, tz=timezone.utc).minute

    if profile.skip_neutral_temps and minutes >= 55:
        rT.reason += f"; Canceling temp at {minutes}m past the hour. "
        return set_temp_basal(0.0, 0, profile, rT, currenttemp)

    if eventualBG < min_bg:
        rT.reason += f"Eventual BG {convert_bg(eventualBG)} < {convert_bg(min_bg)}"
        if minDelta > expectedDelta and minDelta > 0 and carbsReq == 0:
            if naive_eventualBG < 2.2:
                rT.reason += ", naive_eventualBG < 2.2. "
                return set_temp_basal(0.0, 30, profile, rT, currenttemp)
            if glucose_status.delta > minDelta:
                rT.reason += f", but Delta {convert_bg(float(tick))} > expectedDelta {convert_bg(expectedDelta)}"
            else:
                rT.reason += f", but Min. Delta {to_fixed2(minDelta)} > Exp. Delta {convert_bg(expectedDelta)}"
            if currenttemp.duration > 15 and abs(basal - currenttemp.rate) < 1e-9:
                rT.reason += f", temp {currenttemp.rate} ~ req {without_zeros(round_dec(basal, 2))}U/hr. "
                return rT
            else:
                rT.reason += (
                    f"; setting current basal of {round_dec(basal, 2)} as temp. "
                )
                return set_temp_basal(basal, 30, profile, rT, currenttemp)

        insulinReq = 2 * min(0.0, (eventualBG - target_bg) / sens)
        insulinReq = round_dec(insulinReq, 2)
        naiveInsulinReq = min(0.0, (naive_eventualBG - target_bg) / sens)
        naiveInsulinReq = round_dec(naiveInsulinReq, 2)
        if minDelta < 0 and minDelta > expectedDelta:
            newinsulinReq = round_dec((insulinReq * (minDelta / expectedDelta)), 2)
            insulinReq = newinsulinReq

        rate = basal + (2 * insulinReq)
        rate = rate

        insulinScheduled = currenttemp.duration * (currenttemp.rate - basal) / 60
        minInsulinReq = min(insulinReq, naiveInsulinReq)
        if insulinScheduled < minInsulinReq - basal * 0.3:
            rT.reason += f", {currenttemp.duration}m@{to_fixed2(currenttemp.rate)} is a lot less than needed. "
            return set_temp_basal(rate, 30, profile, rT, currenttemp)
        if currenttemp.duration > 5 and rate >= currenttemp.rate * 0.8:
            rT.reason += f", temp {currenttemp.rate} ~< req {round_dec(rate, 2)}U/hr. "
            return rT
        else:
            if rate <= 0:
                bgUndershoot = target_bg - naive_eventualBG
                worstCaseInsulinReq = bgUndershoot / sens
                durationReq = round(60 * worstCaseInsulinReq / profile.current_basal)
                if durationReq < 0:
                    durationReq = 0
                else:
                    durationReq = round(durationReq / 30) * 30
                    durationReq = min(120, max(0, durationReq))
                if durationReq > 0:
                    rT.reason += f", setting {durationReq}m zero temp. "
                    return set_temp_basal(rate, durationReq, profile, rT, currenttemp)
            else:
                rT.reason += f", setting {round_dec(rate, 2)}U/hr. "
            return set_temp_basal(rate, 30, profile, rT, currenttemp)

    if minDelta < expectedDelta:
        if not (microBolusAllowed and enableSMB):
            if glucose_status.delta < minDelta:
                rT.reason += (
                    f"Eventual BG {convert_bg(eventualBG)} > {convert_bg(min_bg)} "
                    f"but Delta {convert_bg(float(tick))} < Exp. Delta {convert_bg(expectedDelta)}"
                )
            else:
                rT.reason += (
                    f"Eventual BG {convert_bg(eventualBG)} > {convert_bg(min_bg)} "
                    f"but Min. Delta {to_fixed2(minDelta)} < Exp. Delta {convert_bg(expectedDelta)}"
                )
            if currenttemp.duration > 15 and abs(basal - currenttemp.rate) < 1e-9:
                rT.reason += f", temp {currenttemp.rate} ~ req {without_zeros(round_dec(basal, 2))}U/hr. "
                return rT
            else:
                rT.reason += (
                    f"; setting current basal of {round_dec(basal, 2)} as temp. "
                )
                return set_temp_basal(basal, 30, profile, rT, currenttemp)

    if min(eventualBG, minPredBG) < max_bg:
        if not (microBolusAllowed and enableSMB):
            rT.reason += f"{convert_bg(eventualBG)}-{convert_bg(minPredBG)} in range: no temp required"
            if currenttemp.duration > 15 and abs(basal - currenttemp.rate) < 1e-9:
                rT.reason += f", temp {currenttemp.rate} ~ req {without_zeros(round_dec(basal, 2))}U/hr. "
                return rT
            else:
                rT.reason += (
                    f"; setting current basal of {round_dec(basal, 2)} as temp. "
                )
                return set_temp_basal(basal, 30, profile, rT, currenttemp)

    if eventualBG >= max_bg:
        rT.reason += f"Eventual BG {convert_bg(eventualBG)} >= {convert_bg(max_bg)}, "
    if iob_data.iob > max_iob:
        rT.reason += f"IOB {round_dec(iob_data.iob, 2)} > max_iob {max_iob}"
        if currenttemp.duration > 15 and abs(basal - currenttemp.rate) < 1e-9:
            rT.reason += f", temp {currenttemp.rate} ~ req {without_zeros(round_dec(basal, 2))}U/hr. "
            return rT
        else:
            rT.reason += f"; setting current basal of {round_dec(basal, 2)} as temp. "
            return set_temp_basal(basal, 30, profile, rT, currenttemp)
    else:
        insulinReq = round_dec((min(minPredBG, eventualBG) - target_bg) / sens, 2)
        if insulinReq > max_iob - iob_data.iob:
            rT.reason += f"max_iob {max_iob}, "
            insulinReq = max_iob - iob_data.iob

        rate = basal + (2 * insulinReq)
        rate = rate
        insulinReq = round_dec(insulinReq, 3)
        rT.insulinReq = insulinReq

        if microBolusAllowed and enableSMB and bg > threshold:
            mealInsulinReq = round_dec(meal_data.meal_cob / profile.carb_ratio, 3)
            smb_max_range = smb_max_range_extension
            if iob_data.iob > mealInsulinReq and iob_data.iob > 0:
                consoleError.append(
                    f"IOB {iob_data.iob} > COB {meal_data.meal_cob}; mealInsulinReq = {mealInsulinReq}"
                )
                consoleError.append(
                    f"profile.maxUAMSMBBasalMinutes: {profile.maxUAMSMBBasalMinutes} profile.current_basal: {profile.current_basal}"
                )
                maxBolus = round_dec(
                    smb_max_range
                    * profile.current_basal
                    * profile.maxUAMSMBBasalMinutes
                    / 60,
                    1,
                )
            else:
                consoleError.append(
                    f"profile.maxSMBBasalMinutes: {profile.maxSMBBasalMinutes} profile.current_basal: {profile.current_basal}"
                )
                maxBolus = round_dec(
                    smb_max_range
                    * profile.current_basal
                    * profile.maxSMBBasalMinutes
                    / 60,
                    1,
                )

            roundSMBTo = 1 / profile.bolus_increment
            microBolus = (
                math.floor(min(insulinReq / 2, maxBolus) * roundSMBTo) / roundSMBTo
            )
            if autoIsfMode:
                microBolus = min(insulinReq * smb_ratio, maxBolus)
                if microBolus > iobTHvirtual - iob_data.iob and loop_wanted_smb in (
                    "fullLoop",
                    "enforced",
                ):
                    microBolus = iobTHvirtual - iob_data.iob
                    consoleError.append(
                        f"Full loop capped SMB at {round_dec(microBolus, 2)} to not exceed {iobTHtolerance}% of effective iobTH {round_dec(iobTHvirtual / iobTHtolerance * 100, 2)}U"
                    )
                microBolus = math.floor(microBolus * roundSMBTo) / roundSMBTo

            smbTarget = target_bg
            worstCaseInsulinReq = (
                smbTarget - (naive_eventualBG + minIOBPredBG) / 2.0
            ) / sens
            durationReq = round(60 * worstCaseInsulinReq / profile.current_basal)
            durationReq = round(durationReq / 30) * 30
            durationReq = min(120, max(0, durationReq))

            rT.rate = basal
            rT.duration = durationReq
            rT.reason += (
                f" SMB: {microBolus}U, setting temp {basal}U/hr for {durationReq}m"
            )
            return rT
        else:
            if currenttemp.duration > 15 and abs(basal - currenttemp.rate) < 1e-9:
                rT.reason += f" temp {currenttemp.rate} ~ req {without_zeros(round_dec(basal, 2))}U/hr. "
                return rT
            else:
                rT.reason += (
                    f"; setting current basal of {round_dec(basal, 2)} as temp. "
                )
                return set_temp_basal(basal, 30, profile, rT, currenttemp)
