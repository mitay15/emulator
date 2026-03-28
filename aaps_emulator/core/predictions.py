# aaps_emulator/core/predictions.py
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

from aaps_emulator.core.autoisf_structs import IobTotal, AutoIsfInputs
from aaps_emulator.core.utils import round_half_even


# ---------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ---------------------------------------------------------
def _round(value: float, digits: int = 0) -> float:
    if value is None:
        return float("nan")
    try:
        if isinstance(value, float) and math.isnan(value):
            return float("nan")
    except Exception:
        pass
    return round_half_even(value, digits)


def _round_int(value: float) -> int:
    return int(round_half_even(value, 0))


def clamp_bg(x: float) -> float:
    """Ограничение BG в диапазоне AAPS [39..401]."""
    try:
        xv = float(x)
    except Exception:
        return 39.0
    if math.isnan(xv):
        return 39.0
    return max(39.0, min(401.0, xv))


def trim_flat_tail(arr: List[float], min_len: int) -> List[float]:
    """
    Удаляет хвост массива, если последние элементы одинаковые.
    AAPS делает это для IOB/COB/UAM/ЗТ массивов.
    """
    for i in range(len(arr) - 1, min_len, -1):
        if arr[i - 1] != arr[i]:
            break
        arr.pop()
    return arr


def compute_bgi(activity: float, sens: float) -> float:
    """BGI = -activity * sens * 5min."""
    return _round(-activity * sens * 5.0, 2)


# ---------------------------------------------------------
# РЕЗУЛЬТАТ ПРЕДСКАЗАНИЙ
# ---------------------------------------------------------
@dataclass
class PredictionsResult:
    eventual_bg: Optional[float] = None
    min_pred_bg: Optional[float] = None
    min_guard_bg: Optional[float] = None

    pred_iob: List[int] = field(default_factory=list)
    pred_cob: List[int] = field(default_factory=list)
    pred_uam: List[int] = field(default_factory=list)
    pred_zt: List[int] = field(default_factory=list)


# ---------------------------------------------------------
# ОСНОВНАЯ ФУНКЦИЯ ПРЕДСКАЗАНИЙ
# ---------------------------------------------------------
def run_predictions(
    inputs: AutoIsfInputs, profile_util_convert_bg=lambda x: f"{x:.0f}"
) -> PredictionsResult:

    gs = inputs.glucose_status
    profile = inputs.profile

    # -----------------------------------------------------
    # ПОДГОТОВКА IOB
    # -----------------------------------------------------
    iob_array = inputs.iob_data_array or []
    if not iob_array:
        iob_array = [IobTotal(iob=0.0, activity=0.0, lastBolusTime=0)]

    orig_iob_tick = iob_array[0]

    # -----------------------------------------------------
    # ПОДГОТОВКА ОСНОВНЫХ ПАРАМЕТРОВ
    # -----------------------------------------------------
    bg = getattr(gs, "glucose", 0.0)
    min_bg = getattr(profile, "min_bg", 0.0)
    max_bg = getattr(profile, "max_bg", 0.0)
    target_bg = (min_bg + max_bg) / 2.0

    # Sensitivity (AutoISF)
    autosens_ratio = getattr(inputs.autosens, "ratio", 1.0)
    base_sens = float(getattr(profile, "sens", 100.0) or 100.0)
    sens = _round(base_sens * autosens_ratio, 1)

    # -----------------------------------------------------
    # BGI
    # -----------------------------------------------------
    activity_for_bgi = float(getattr(orig_iob_tick, "activity", 0.0) or 0.0)
    bgi = compute_bgi(activity_for_bgi, sens)

    # -----------------------------------------------------
    # DEVIATION
    # -----------------------------------------------------
    horizon_min = 30.0 * float(autosens_ratio or 1.0)
    delta = getattr(gs, "delta", 0.0)
    short = getattr(gs, "shortAvgDelta", 0.0)
    long = getattr(gs, "longAvgDelta", 0.0)

    deviation = _round(horizon_min / 5.0 * (min(delta, short) - bgi), 0)
    if deviation < 0:
        deviation = _round(horizon_min / 5.0 * (min(short, long) - bgi), 0)
        if deviation < 0:
            deviation = _round(horizon_min / 5.0 * (long - bgi), 0)

    # -----------------------------------------------------
    # NAIVE eventual BG
    # -----------------------------------------------------
    naive_eventualBG = _round(bg - (orig_iob_tick.iob * sens), 0)
    eventualBG = naive_eventualBG + deviation

    # -----------------------------------------------------
    # ИНИЦИАЛИЗАЦИЯ МАССИВОВ ПРЕДСКАЗАНИЙ
    # -----------------------------------------------------
    IOBpredBGs = [bg]
    COBpredBGs = [bg]
    UAMpredBGs = [bg]
    ZTpredBGs = [bg]

    
    # -----------------------------------------------------
    # ОСНОВНОЙ ЦИКЛ ПРЕДСКАЗАНИЙ
    # -----------------------------------------------------
    for iobTick in iob_array:
        activity = float(getattr(iobTick, "activity", 0.0) or 0.0)
        activity_zt = float(
            getattr(getattr(iobTick, "iobWithZeroTemp", iobTick), "activity", 0.0) or 0.0
        )

        predBGI = compute_bgi(activity, sens)
        predZTBGI = compute_bgi(activity_zt, sens)

        # IOB
        IOBpredBG = IOBpredBGs[-1] + predBGI
        IOBpredBGs.append(IOBpredBG)

        # ZT
        ZTpredBG = ZTpredBGs[-1] + predZTBGI
        ZTpredBGs.append(ZTpredBG)

        # UAM
        UAMpredBG = UAMpredBGs[-1] + predBGI
        UAMpredBGs.append(UAMpredBG)

        # COB (упрощённая версия AAPS)
        COBpredBG = COBpredBGs[-1] + predBGI
        COBpredBGs.append(COBpredBG)

    # -----------------------------------------------------
    # ФИНАЛИЗАЦИЯ МАССИВОВ
    # -----------------------------------------------------
    IOBpredBGs = [int(_round(clamp_bg(x), 0)) for x in IOBpredBGs]
    ZTpredBGs = [int(_round(clamp_bg(x), 0)) for x in ZTpredBGs]
    UAMpredBGs = [int(_round(clamp_bg(x), 0)) for x in UAMpredBGs]
    COBpredBGs = [int(_round(clamp_bg(x), 0)) for x in COBpredBGs]

    IOBpredBGs = trim_flat_tail(IOBpredBGs, 12)
    ZTpredBGs = trim_flat_tail(ZTpredBGs, 6)
    UAMpredBGs = trim_flat_tail(UAMpredBGs, 12)
    COBpredBGs = trim_flat_tail(COBpredBGs, 12)

    # -----------------------------------------------------
    # MIN / GUARD BG
    # -----------------------------------------------------
    min_pred_bg = min(IOBpredBGs + UAMpredBGs + ZTpredBGs + COBpredBGs)
    min_guard_bg = min(IOBpredBGs + ZTpredBGs)

    # -----------------------------------------------------
    # EVENTUAL BG (AAPS‑style)
    # -----------------------------------------------------
    eventual = eventualBG
    eventual = max(eventual, min_pred_bg)
    eventual = max(eventual, min_guard_bg)
    eventual = max(eventual, _round(target_bg, 0))
    eventual = int(clamp_bg(eventual))

    # -----------------------------------------------------
    # РЕЗУЛЬТАТ
    # -----------------------------------------------------
    res = PredictionsResult()
    res.pred_iob = IOBpredBGs
    res.pred_cob = COBpredBGs
    res.pred_uam = UAMpredBGs
    res.pred_zt = ZTpredBGs

    res.min_pred_bg = float(min_pred_bg)
    res.min_guard_bg = float(min_guard_bg)
    res.eventual_bg = eventual

    return res
