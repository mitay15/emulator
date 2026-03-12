# aaps_emulator/runner/build_inputs.py
from __future__ import annotations

import json
import logging
import traceback
from pathlib import Path
from typing import Any, Dict, List

from aaps_emulator.core.autoisf_structs import (
    AutoIsfInputs,
    AutosensResult,
    GlucoseStatusAutoIsf,
    IobTotal,
    MealData,
    OapsProfileAutoIsf,
    TempBasal,
)

logger = logging.getLogger(__name__)


# ----------------------------
# Безопасные конвертеры
# ----------------------------
def _safe_float(v):
    try:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(",", ".")
        return float(s)
    except Exception:
        return None


def _safe_int(v):
    try:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        s = str(v).strip().replace(",", ".")
        return int(float(s))
    except Exception:
        return None


# ----------------------------
# Конвертация объектов
# ----------------------------
def _to_glucose_status(obj: Dict[str, Any]) -> GlucoseStatusAutoIsf:
    if not obj:
        return GlucoseStatusAutoIsf()

    try:
        return GlucoseStatusAutoIsf(
            glucose=_safe_float(obj.get("glucose")),
            delta=_safe_float(obj.get("delta")),
            shortAvgDelta=_safe_float(obj.get("shortAvgDelta")),
            longAvgDelta=_safe_float(obj.get("longAvgDelta")),
            date=_safe_int(obj.get("date")),
            noise=_safe_int(obj.get("noise")),
            bgAcceleration=_safe_float(obj.get("bgAcceleration")),
            duraISFminutes=_safe_float(obj.get("duraISFminutes")),
            duraISFaverage=_safe_float(obj.get("duraISFaverage")),
            parabolaMinutes=_safe_float(obj.get("parabolaMinutes")),
            deltaPl=_safe_float(obj.get("deltaPl")),
            deltaPn=_safe_float(obj.get("deltaPn")),
            a0=_safe_float(obj.get("a0")),
            a1=_safe_float(obj.get("a1")),
            a2=_safe_float(obj.get("a2")),
            corrSqu=_safe_float(obj.get("corrSqu")),
            raw=obj,
        )
    except Exception:
        logger.exception("Failed to convert glucose status object")
        return GlucoseStatusAutoIsf()


def _to_current_temp(obj: Dict[str, Any]) -> TempBasal:
    if not obj:
        return TempBasal()

    try:
        return TempBasal(
            duration=_safe_int(obj.get("duration")),
            rate=_safe_float(obj.get("rate")),
            minutesrunning=_safe_int(obj.get("minutesrunning")),
            created_at=_safe_int(obj.get("created_at")),
            raw=obj,
        )
    except Exception:
        logger.exception("Failed to convert current temp object")
        return TempBasal()


def _to_iob(od: Dict[str, Any]) -> IobTotal:
    if not od:
        return IobTotal()

    try:
        # Вложенный iobWithZeroTemp может быть dict или None
        iwt = od.get("iobWithZeroTemp")
        # Передаём iobWithZeroTemp как есть — конструктор IobTotal обработает dict/None/obj
        return IobTotal(
            iob=_safe_float(od.get("iob")),
            activity=_safe_float(od.get("activity")),
            lastBolusTime=_safe_int(od.get("lastBolusTime")),
            iobWithZeroTemp=iwt,
            raw={
                k: v
                for k, v in od.items()
                if k not in {"iob", "activity", "lastBolusTime", "iobWithZeroTemp"}
            },
        )
    except Exception:
        logger.exception("Failed to convert IobTotal object")
        return IobTotal()


def _to_profile(d: Dict[str, Any]) -> OapsProfileAutoIsf:
    if not d:
        return OapsProfileAutoIsf()

    try:
        # если OapsProfileAutoIsf принимает kwargs, можно предварительно привести ключевые поля
        d2 = dict(d)
        # приведение некоторых числовых полей
        for k in (
            "min_bg",
            "max_bg",
            "sens",
            "variable_sens",
            "current_basal",
            "max_iob",
            "lgsThreshold",
        ):
            if k in d2:
                if k == "lgsThreshold":
                    d2[k] = _safe_float(d2.get(k))  # может быть None
                else:
                    d2[k] = _safe_float(d2.get(k)) or d2.get(k)
        return OapsProfileAutoIsf(**d2)
    except Exception:
        logger.exception("Failed to convert profile object")
        return OapsProfileAutoIsf()


def _to_autosens(d: Dict[str, Any]) -> AutosensResult:
    if not d:
        return AutosensResult()

    try:
        return AutosensResult(**d)
    except Exception:
        logger.exception("Failed to convert autosens object")
        return AutosensResult()


def _to_meal(d: Dict[str, Any]) -> MealData:
    if not d:
        return MealData()

    try:
        return MealData(
            carbs=_safe_float(d.get("carbs")),
            mealCOB=_safe_float(d.get("mealCOB")),
            lastCarbTime=_safe_int(d.get("lastCarbTime")),
            slopeFromMaxDeviation=_safe_float(d.get("slopeFromMaxDeviation")),
            slopeFromMinDeviation=_safe_float(d.get("slopeFromMinDeviation")),
            raw=d,
        )
    except Exception:
        logger.exception("Failed to convert meal object")
        return MealData()


# ----------------------------
# Главный сборщик входов
# ----------------------------
def build_inputs_from_block(block: List[Dict[str, Any]]) -> AutoIsfInputs:
    """
    Преобразует список объектов AutoISF-блока из логов AAPS
    в корректный AutoIsfInputs (core.autoisf_structs).
    Исправлена ошибка: используем параметр `block` везде (не block_objs).
    Также: если в RT есть variable_sens, переносим его в profile.
    """

    try:
        # Ищем объекты по типам в переданном block (не block_objs)
        gs_obj = next(
            (
                o
                for o in block
                if isinstance(o, dict) and o.get("__type__") == "GlucoseStatusAutoIsf"
            ),
            {},
        )
        ct_obj = next(
            (
                o
                for o in block
                if isinstance(o, dict) and o.get("__type__") == "CurrentTemp"
            ),
            {},
        )
        rt_obj = next(
            (o for o in block if isinstance(o, dict) and o.get("__type__") == "RT"), {}
        )

        profile_obj = (
            rt_obj.get("profile") if isinstance(rt_obj, dict) else None
        ) or next(
            (
                o
                for o in block
                if isinstance(o, dict) and o.get("__type__") == "OapsProfileAutoIsf"
            ),
            {},
        )
        autosens_obj = (
            rt_obj.get("autosens") if isinstance(rt_obj, dict) else None
        ) or next(
            (
                o
                for o in block
                if isinstance(o, dict) and o.get("__type__") == "AutosensResult"
            ),
            {},
        )
        meal_obj = (
            rt_obj.get("mealData") if isinstance(rt_obj, dict) else None
        ) or next(
            (
                o
                for o in block
                if isinstance(o, dict) and o.get("__type__") == "MealData"
            ),
            {},
        )

        iob_objs = [
            o for o in block if isinstance(o, dict) and o.get("__type__") == "IobTotal"
        ]

        # Конвертация в core-структуры (оборачиваем вызовы в try, чтобы локализовать ошибки)
        try:
            gs = _to_glucose_status(gs_obj)
        except Exception:
            gs = None

        try:
            ct = _to_current_temp(ct_obj)
        except Exception:
            ct = None

        try:
            profile = _to_profile(profile_obj)
            # --- propagate RT.variable_sens into profile ---
            try:
                if isinstance(rt_obj, dict) and profile is not None:
                    vs_rt = rt_obj.get("variable_sens") or rt_obj.get("variableSens")
                    if vs_rt is not None:
                        profile.variable_sens = vs_rt
                        setattr(profile, "_variable_sens_from_rt", True)
                        print("DEBUG: RT variable_sens propagated into profile:", vs_rt)
            except Exception as e:
                print("DEBUG: propagate RT variable_sens failed:", e)
            # ------------------------------------------------

        except Exception:
            profile = None

        try:
            autosens = _to_autosens(autosens_obj)
            # --- propagate RT.variable_sens into autosens if present ---
            try:
                if isinstance(rt_obj, dict) and autosens is not None:
                    vs_rt = rt_obj.get("variable_sens") or rt_obj.get("variableSens")
                    if vs_rt is not None:
                        autosens.ratio = vs_rt
                        setattr(autosens, "_variable_sens_from_rt", True)
                        print(
                            "DEBUG: RT variable_sens propagated into autosens:", vs_rt
                        )
            except Exception as e:
                print("DEBUG: propagate RT variable_sens into autosens failed:", e)
            # -----------------------------------------------------------

        except Exception:
            autosens = None

        try:
            meal = _to_meal(meal_obj)
        except Exception:
            meal = None

        iob_array = []
        for o in iob_objs:
            try:
                iob_array.append(_to_iob(o))
            except Exception:
                # если один iob не конвертируется — пропускаем, но продолжаем
                continue

        # Собираем итоговый AutoIsfInputs
        return AutoIsfInputs(
            glucose_status=gs,
            current_temp=ct,
            iob_data_array=iob_array,
            profile=profile,
            autosens=autosens,
            meal=meal,
            rt=rt_obj if isinstance(rt_obj, dict) else {},
            raw_block=block,
        )

    except Exception as exc:
        # Логируем ошибку и сохраняем дамп для отладки
        try:
            cache_dir = Path(__file__).parent.parent / "data" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            out = cache_dir / "parsed_block_on_error.json"
            with out.open("w", encoding="utf-8") as f:
                json.dump(
                    {
                        "error": str(exc),
                        "trace": traceback.format_exc(),
                        "block": block,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.error(f"Error while building inputs, dump saved to {out}")
        except Exception:
            logger.exception("Failed to write error dump for build_inputs")
        raise
