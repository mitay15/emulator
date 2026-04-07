# aaps_emulator/core/autoisf_structs.py
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional, Tuple


def safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    """
    Safe attribute/key getter used across the codebase.
    Works for dataclasses/objects with attributes and for dicts.
    """
    try:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)
    except Exception:
        return default


class _BaseStruct:
    """
    Базовый класс для всех структур с полями raw/extras.
    Даёт единое поведение:
    - сохраняем исходный kwargs в raw
    - известные поля пишем в атрибуты
    - остальные — в extras
    """

    def _init_from_kwargs(self, kwargs: Dict[str, Any]) -> None:
        raw_copy = dict(kwargs)
        object.__setattr__(self, "raw", raw_copy)

        known = {f.name for f in fields(self)}
        extras: Dict[str, Any] = {}

        for k, v in list(kwargs.items()):
            if k in known:
                try:
                    setattr(self, k, v)
                except Exception:
                    # игнорируем неудачные присваивания, но не падаем
                    pass
            else:
                extras[k] = v

        object.__setattr__(self, "extras", extras)


# -------------------------
# Core data structures
# -------------------------
@dataclass
class IobTotal(_BaseStruct):
    """
    Compatible structure for total IOB/activity similar to AAPS.
    Accepts arbitrary kwargs in constructor; known fields are set,
    unknown fields are stored in extras. The original raw dict is
    stored in `raw` for debugging/dumps.
    """

    iob: float = 0.0
    activity: float = 0.0
    iobWithZeroTemp: Optional["IobTotal"] = None
    lastBolusTime: int = 0
    timestamp: Optional[int] = None

    raw: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)

    __type__: str = "IobTotal"

    def __init__(self, **kwargs: Any) -> None:
        object.__setattr__(self, "iob", 0.0)
        object.__setattr__(self, "activity", 0.0)
        object.__setattr__(self, "iobWithZeroTemp", None)
        object.__setattr__(self, "lastBolusTime", 0)
        object.__setattr__(self, "timestamp", None)
        object.__setattr__(self, "raw", {})
        object.__setattr__(self, "extras", {})
        object.__setattr__(self, "__type__", "IobTotal")

        # отдельная обработка iobWithZeroTemp
        iwt = kwargs.pop("iobWithZeroTemp", None)

        # стандартная инициализация известных/extra полей
        self._init_from_kwargs(kwargs)

        # обработка iobWithZeroTemp после основного init
        if isinstance(iwt, dict):
            try:
                self.iobWithZeroTemp = IobTotal(**iwt)
            except Exception:
                self.iobWithZeroTemp = None
                self.extras["iobWithZeroTemp_raw"] = iwt
        elif isinstance(iwt, IobTotal):
            self.iobWithZeroTemp = iwt
        else:
            self.iobWithZeroTemp = None


@dataclass
class GlucoseStatusAutoIsf(_BaseStruct):
    glucose: Optional[float] = None
    delta: Optional[float] = None
    shortAvgDelta: Optional[float] = None
    longAvgDelta: Optional[float] = None
    date: Optional[int] = None
    noise: Optional[float] = None

    # parabola / regression fields
    bgAcceleration: Optional[float] = None
    duraISFminutes: Optional[float] = None
    duraISFaverage: Optional[float] = None
    parabolaMinutes: Optional[float] = None
    deltaPl: Optional[float] = None
    deltaPn: Optional[float] = None
    a0: Optional[float] = None
    a1: Optional[float] = None
    a2: Optional[float] = None
    corrSqu: Optional[float] = None

    raw: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)

    __type__: str = "GlucoseStatusAutoIsf"

    def __init__(self, **kwargs: Any) -> None:
        # дефолты
        object.__setattr__(self, "glucose", None)
        object.__setattr__(self, "delta", None)
        object.__setattr__(self, "shortAvgDelta", None)
        object.__setattr__(self, "longAvgDelta", None)
        object.__setattr__(self, "date", None)
        object.__setattr__(self, "noise", None)
        object.__setattr__(self, "bgAcceleration", None)
        object.__setattr__(self, "duraISFminutes", None)
        object.__setattr__(self, "duraISFaverage", None)
        object.__setattr__(self, "parabolaMinutes", None)
        object.__setattr__(self, "deltaPl", None)
        object.__setattr__(self, "deltaPn", None)
        object.__setattr__(self, "a0", None)
        object.__setattr__(self, "a1", None)
        object.__setattr__(self, "a2", None)
        object.__setattr__(self, "corrSqu", None)
        object.__setattr__(self, "raw", {})
        object.__setattr__(self, "extras", {})
        object.__setattr__(self, "__type__", "GlucoseStatusAutoIsf")

        self._init_from_kwargs(kwargs)


@dataclass
class TempBasal(_BaseStruct):
    duration: Optional[int] = None
    rate: Optional[float] = None
    minutesrunning: Optional[int] = None
    created_at: Optional[int] = None

    raw: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)

    __type__: str = "CurrentTemp"

    def __init__(self, **kwargs: Any) -> None:
        object.__setattr__(self, "duration", None)
        object.__setattr__(self, "rate", None)
        object.__setattr__(self, "minutesrunning", None)
        object.__setattr__(self, "created_at", None)
        object.__setattr__(self, "raw", {})
        object.__setattr__(self, "extras", {})
        object.__setattr__(self, "__type__", "CurrentTemp")

        self._init_from_kwargs(kwargs)


@dataclass
class OapsProfileAutoIsf(_BaseStruct):
    # basic targets
    min_bg: Optional[float] = None
    max_bg: Optional[float] = None
    target_bg: Optional[float] = None

    # basal / limits
    current_basal: Optional[float] = None
    max_basal: Optional[float] = None
    max_daily_basal: Optional[float] = None
    max_daily_safety_multiplier: Optional[float] = None
    current_basal_safety_multiplier: Optional[float] = None

    # sensitivity
    sens: Optional[float] = None
    variable_sens: Optional[float] = None
    autosens_max: Optional[float] = None
    autosens_min: Optional[float] = None

    # AutoISF settings
    enable_autoISF: Optional[bool] = True
    autoISF_min: Optional[float] = None
    autoISF_max: Optional[float] = None
    autoISF_version: Optional[int] = None

    # weights
    bgAccel_ISF_weight: Optional[float] = None
    bgBrake_ISF_weight: Optional[float] = None
    pp_ISF_weight: Optional[float] = None
    dura_ISF_weight: Optional[float] = None
    lower_ISFrange_weight: Optional[float] = None
    higher_ISFrange_weight: Optional[float] = None

    # carbs / SMB
    carb_ratio: Optional[float] = None
    smb_delivery_ratio: Optional[float] = None
    smb_delivery_ratio_min: Optional[float] = None
    smb_delivery_ratio_max: Optional[float] = None
    smb_delivery_ratio_bg_range: Optional[Tuple[float, float]] = None
    bolus_increment: Optional[float] = None
    maxSMBBasalMinutes: Optional[int] = None
    maxUAMSMBBasalMinutes: Optional[int] = None

    # other flags
    enableUAM: Optional[bool] = False
    high_temptarget_raises_sensitivity: Optional[bool] = False
    low_temptarget_lowers_sensitivity: Optional[bool] = False
    temptargetSet: Optional[bool] = False

    # safety / thresholds
    lgsThreshold: Optional[float] = None
    max_iob: Optional[float] = None
    iob_threshold_percent: Optional[float] = None

    # доп. поля, которые могут приходить из профиля AAPS
    half_basal_exercise_target: Optional[float] = None

    raw: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)

    __type__: str = "OapsProfileAutoIsf"

    def __init__(self, **kwargs: Any) -> None:
        # дефолты
        object.__setattr__(self, "min_bg", None)
        object.__setattr__(self, "max_bg", None)
        object.__setattr__(self, "target_bg", None)
        object.__setattr__(self, "current_basal", None)
        object.__setattr__(self, "max_basal", None)
        object.__setattr__(self, "max_daily_basal", None)
        object.__setattr__(self, "max_daily_safety_multiplier", None)
        object.__setattr__(self, "current_basal_safety_multiplier", None)
        object.__setattr__(self, "sens", None)
        object.__setattr__(self, "variable_sens", None)
        object.__setattr__(self, "autosens_max", None)
        object.__setattr__(self, "autosens_min", None)
        object.__setattr__(self, "enable_autoISF", True)
        object.__setattr__(self, "autoISF_min", None)
        object.__setattr__(self, "autoISF_max", None)
        object.__setattr__(self, "autoISF_version", None)
        object.__setattr__(self, "bgAccel_ISF_weight", None)
        object.__setattr__(self, "bgBrake_ISF_weight", None)
        object.__setattr__(self, "pp_ISF_weight", None)
        object.__setattr__(self, "dura_ISF_weight", None)
        object.__setattr__(self, "lower_ISFrange_weight", None)
        object.__setattr__(self, "higher_ISFrange_weight", None)
        object.__setattr__(self, "carb_ratio", None)
        object.__setattr__(self, "smb_delivery_ratio", None)
        object.__setattr__(self, "smb_delivery_ratio_min", None)
        object.__setattr__(self, "smb_delivery_ratio_max", None)
        object.__setattr__(self, "smb_delivery_ratio_bg_range", None)
        object.__setattr__(self, "bolus_increment", None)
        object.__setattr__(self, "maxSMBBasalMinutes", None)
        object.__setattr__(self, "maxUAMSMBBasalMinutes", None)
        object.__setattr__(self, "enableUAM", False)
        object.__setattr__(self, "high_temptarget_raises_sensitivity", False)
        object.__setattr__(self, "low_temptarget_lowers_sensitivity", False)
        object.__setattr__(self, "temptargetSet", False)
        object.__setattr__(self, "lgsThreshold", None)
        object.__setattr__(self, "max_iob", None)
        object.__setattr__(self, "iob_threshold_percent", None)
        object.__setattr__(self, "half_basal_exercise_target", None)
        object.__setattr__(self, "raw", {})
        object.__setattr__(self, "extras", {})
        object.__setattr__(self, "__type__", "OapsProfileAutoIsf")

        self._init_from_kwargs(kwargs)


@dataclass
class AutosensResult(_BaseStruct):
    ratio: Optional[float] = None
    carb_ratio_adjustment: Optional[float] = None
    sens_adjustment: Optional[float] = None
    raw: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)
    __type__: str = "AutosensResult"

    def __init__(self, **kwargs: Any) -> None:
        object.__setattr__(self, "ratio", None)
        object.__setattr__(self, "carb_ratio_adjustment", None)
        object.__setattr__(self, "sens_adjustment", None)
        object.__setattr__(self, "raw", {})
        object.__setattr__(self, "extras", {})
        object.__setattr__(self, "__type__", "AutosensResult")

        self._init_from_kwargs(kwargs)


@dataclass
class MealData(_BaseStruct):
    carbs: Optional[float] = None
    mealCOB: Optional[float] = None
    lastCarbTime: Optional[int] = None
    slopeFromMaxDeviation: Optional[float] = None
    slopeFromMinDeviation: Optional[float] = None

    raw: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)
    __type__: str = "MealData"

    def __init__(self, **kwargs: Any) -> None:
        object.__setattr__(self, "carbs", None)
        object.__setattr__(self, "mealCOB", None)
        object.__setattr__(self, "lastCarbTime", None)
        object.__setattr__(self, "slopeFromMaxDeviation", None)
        object.__setattr__(self, "slopeFromMinDeviation", None)
        object.__setattr__(self, "raw", {})
        object.__setattr__(self, "extras", {})
        object.__setattr__(self, "__type__", "MealData")

        self._init_from_kwargs(kwargs)


# -------------------------
# Pipeline input / output containers
# -------------------------
@dataclass
class AutoIsfInputs:
    glucose_status: Optional[GlucoseStatusAutoIsf] = None
    current_temp: Optional[TempBasal] = None
    iob_data_array: List[IobTotal] = field(default_factory=list)
    profile: Optional[OapsProfileAutoIsf] = None
    autosens: Optional[AutosensResult] = None
    meal: Optional[MealData] = None
    rt: Dict[str, Any] = field(default_factory=dict)
    raw_block: Any = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Универсальная сериализация AutoIsfInputs → dict.
        Работает для вложенных dataclass и обычных dict.
        """
        from dataclasses import asdict, is_dataclass

        def convert(obj):
            if is_dataclass(obj):
                return {k: convert(v) for k, v in asdict(obj).items()}
            if isinstance(obj, list):
                return [convert(x) for x in obj]
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            return obj

        return convert(self)


@dataclass
class DosingResult:
    rate: float = 0.0
    duration: int = 0
    insulinReq: float = 0.0
    units: Optional[float] = None  # microbolus units
    carbsReq: Optional[float] = None
    carbsReqWithin: Optional[int] = None
    smb: Optional[float] = None
    reason: str = ""
    eventualBG: float | None = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CorePredResultAlias:
    bg: Optional[float] = None
    delta: Optional[float] = None
    eventual_bg: Optional[float] = None
    min_pred_bg: Optional[float] = None
    min_guard_bg: Optional[float] = None
    pred_iob: List[int] = field(default_factory=list)
    pred_cob: List[int] = field(default_factory=list)
    pred_uam: List[int] = field(default_factory=list)
    pred_zt: List[int] = field(default_factory=list)
    trace: List[Any] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


# Alias for backward compatibility with tests expecting Profile
Profile = OapsProfileAutoIsf
