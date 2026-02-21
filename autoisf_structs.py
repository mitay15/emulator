from dataclasses import dataclass, field
from typing import List, Optional


# -----------------------------
# Glucose status (mmol/L)
# -----------------------------
@dataclass
class GlucoseStatus:
    glucose: float  # BG in mmol/L
    delta: float  # 5m delta in mmol/L
    short_avg_delta: float  # 15m delta
    long_avg_delta: float  # 40m delta
    date: int  # timestamp (ms)
    noise: float  # CGM noise level


# -----------------------------
# IOB + activity (U, U/min)
# -----------------------------
@dataclass
class IobTotal:
    iob: float  # insulin on board (U)
    activity: float  # insulin activity (U/min)
    iob_with_zero_temp: Optional["IobTotal"] = None


# -----------------------------
# Meal data
# -----------------------------
@dataclass
class MealData:
    carbs: float  # total carbs entered (g)
    meal_cob: float  # current COB (g)
    last_carb_time: int  # timestamp (ms)
    slope_from_max_deviation: float
    slope_from_min_deviation: float


# -----------------------------
# Autosens result
# -----------------------------
@dataclass
class AutosensResult:
    ratio: float = 1.0  # autosens multiplier (0.7–1.2)
    sens_result: str = ""  # text info


# -----------------------------
# Current temp basal
# -----------------------------
@dataclass
class CurrentTemp:
    duration: int  # minutes remaining
    rate: float  # U/hr
    minutes_running: int  # how long temp basal has been running


# -----------------------------
# Predictions (mmol/L)
# -----------------------------
@dataclass
class Predictions:
    IOB: Optional[List[int]] = None
    COB: Optional[List[int]] = None
    aCOB: Optional[List[int]] = None
    UAM: Optional[List[int]] = None
    ZT: Optional[List[int]] = None


# -----------------------------
# AutoISF profile (mmol/L)
# -----------------------------
class OapsProfileAutoIsf:
    def __init__(
        self,
        min_bg=None,
        max_bg=None,
        target_bg=None,
        sens=None,
        carb_ratio=None,
        current_basal=None,
        max_basal=None,
        max_daily_basal=None,
        max_iob=None,
        autosens_max=None,
        sensitivity_raises_target=False,
        resistance_lowers_target=False,
        adv_target_adjustments=False,
        exercise_mode=False,
        high_temptarget_raises_sensitivity=False,
        low_temptarget_lowers_sensitivity=False,
        half_basal_exercise_target=None,
        temptarget_set=False,
        remainingCarbsCap=None,
        bolus_increment=None,
        skip_neutral_temps=False,
        autoISF_version="3.0.1",
        enable_uam=False,
        enableSMB_always=False,
        enableSMB_with_COB=False,
        enableSMB_after_carbs=False,
        enableSMB_with_temptarget=False,
        allowSMB_with_high_temptarget=False,
        SMBInterval=None,
        smb_delivery_ratio=None,
        smb_delivery_ratio_min=None,
        smb_delivery_ratio_max=None,
        smb_delivery_ratio_bg_range=None,
        smb_max_range_extension=None,
        maxSMBBasalMinutes=None,
        maxUAMSMBBasalMinutes=None,
        variable_sens=None,
    ):
        self.min_bg = min_bg
        self.max_bg = max_bg
        self.target_bg = target_bg
        self.sens = sens
        self.carb_ratio = carb_ratio
        self.current_basal = current_basal
        self.max_basal = max_basal
        self.max_daily_basal = max_daily_basal
        self.max_iob = max_iob
        self.autosens_max = autosens_max

        self.sensitivity_raises_target = sensitivity_raises_target
        self.resistance_lowers_target = resistance_lowers_target
        self.adv_target_adjustments = adv_target_adjustments
        self.exercise_mode = exercise_mode
        self.high_temptarget_raises_sensitivity = high_temptarget_raises_sensitivity
        self.low_temptarget_lowers_sensitivity = low_temptarget_lowers_sensitivity
        self.half_basal_exercise_target = half_basal_exercise_target
        self.temptarget_set = temptarget_set
        self.remainingCarbsCap = remainingCarbsCap
        self.bolus_increment = bolus_increment
        self.skip_neutral_temps = skip_neutral_temps

        self.autoISF_version = autoISF_version

        self.enable_uam = enable_uam
        self.enableSMB_always = enableSMB_always
        self.enableSMB_with_COB = enableSMB_with_COB
        self.enableSMB_after_carbs = enableSMB_after_carbs
        self.enableSMB_with_temptarget = enableSMB_with_temptarget
        self.allowSMB_with_high_temptarget = allowSMB_with_high_temptarget

        self.SMBInterval = SMBInterval
        self.smb_delivery_ratio = smb_delivery_ratio
        self.smb_delivery_ratio_min = smb_delivery_ratio_min
        self.smb_delivery_ratio_max = smb_delivery_ratio_max
        self.smb_delivery_ratio_bg_range = smb_delivery_ratio_bg_range
        self.smb_max_range_extension = smb_max_range_extension

        self.maxSMBBasalMinutes = maxSMBBasalMinutes
        self.maxUAMSMBBasalMinutes = maxUAMSMBBasalMinutes

        self.variable_sens = variable_sens


# -----------------------------
# Final result (RT)
# -----------------------------
@dataclass
class RT:
    algorithm: str
    running_dynamic_isf: bool
    timestamp: int

    bg: Optional[float] = None
    tick: Optional[str] = None
    eventual_bg: Optional[float] = None
    target_bg: Optional[float] = None
    insulin_req: Optional[float] = None
    carbs_req: Optional[int] = None
    carbs_req_within: Optional[int] = None

    deliver_at: Optional[int] = None
    sensitivity_ratio: Optional[float] = None

    duration: Optional[int] = None
    rate: Optional[float] = None

    pred_bgs: Optional[Predictions] = None

    cob: Optional[float] = None
    iob: Optional[float] = None
    variable_sens: Optional[float] = None

    reason: str = ""
    console_log: List[str] = field(default_factory=list)
    console_error: List[str] = field(default_factory=list)
