# aaps_emulator/core/autoisf_structs.py
from dataclasses import dataclass
from typing import Optional


@dataclass
class GlucoseStatus:
    glucose: float  # mmol/L
    delta: float  # mmol/L per 5min
    short_avg_delta: float  # mmol/L per 5min
    long_avg_delta: float  # mmol/L per 5min
    date: int  # timestamp ms
    noise: float

    def __str__(self):
        return (
            f"GlucoseStatus(glucose={self.glucose:.2f} mmol/L, delta={self.delta:.2f}, "
            f"shortAvgDelta={self.short_avg_delta:.2f}, longAvgDelta={self.long_avg_delta:.2f}, "
            f"date={self.date}, noise={self.noise})"
        )


@dataclass
class IobTotal:
    iob: float
    activity: float
    iob_with_zero_temp: Optional[object] = None

    def __str__(self):
        return f"IobTotal(iob={self.iob}, activity={self.activity})"


@dataclass
class MealData:
    carbs: float
    meal_cob: float
    last_carb_time: int
    slope_from_max_deviation: float = 0.0
    slope_from_min_deviation: float = 0.0

    def __str__(self):
        return (
            f"MealData(carbs={self.carbs}, mealCOB={self.meal_cob}, "
            f"lastCarbTime={self.last_carb_time})"
        )


@dataclass
class AutosensResult:
    ratio: float
    sens_result: Optional[str] = None

    def __str__(self):
        return f"AutosensResult(ratio={self.ratio}, sens_result={self.sens_result})"


@dataclass
class CurrentTemp:
    duration: int
    rate: float
    minutes_running: int = 0

    def __str__(self):
        return f"CurrentTemp(duration={self.duration}, rate={self.rate})"


@dataclass
class OapsProfileAutoIsf:
    min_bg: float
    max_bg: float
    target_bg: float
    sens: float
    carb_ratio: float
    current_basal: float
    max_basal: float
    max_daily_basal: float
    max_iob: float
    autosens_max: float

    # optional flags and extras
    enable_uam: bool = False
    enableSMB_always: bool = False
    enableSMB_with_COB: bool = False
    enableSMB_after_carbs: bool = False
    enableSMB_with_temptarget: bool = False
    allowSMB_with_high_temptarget: bool = False
    SMBInterval: int = 5
    smb_delivery_ratio: float = 0.5
    smb_delivery_ratio_min: float = 0.5
    smb_delivery_ratio_max: float = 0.6
    smb_delivery_ratio_bg_range: float = 0.0
    smb_max_range_extension: float = 1.0
    maxSMBBasalMinutes: int = 90
    maxUAMSMBBasalMinutes: int = 60
    variable_sens: Optional[float] = None

    # additional fields used in some code paths
    sensitivity_raises_target: bool = False
    resistance_lowers_target: bool = False
    adv_target_adjustments: bool = False
    enable_uam_flag: bool = False

    def __str__(self):
        return (
            f"OapsProfileAutoIsf(target_bg={self.target_bg}, sens={self.sens}, "
            f"carb_ratio={self.carb_ratio}, current_basal={self.current_basal})"
        )
