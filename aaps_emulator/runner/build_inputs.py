# aaps_emulator/runner/build_inputs.py
from __future__ import annotations

import json
import logging
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional
from aaps_emulator.runner.load_logs import load_logs


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


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(",", ".")
        return float(s)
    except Exception:
        return None


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        s = str(v).strip().replace(",", ".")
        return int(float(s))
    except Exception:
        return None


def _find_first(block: List[Dict[str, Any]], type_name: str) -> Dict[str, Any]:
    return next(
        (o for o in block if isinstance(o, dict) and o.get("__type__") == type_name),
        {},
    )


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
        iwt = od.get("iobWithZeroTemp")
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
        d2 = dict(d)
        for k in ("min_bg", "max_bg", "sens", "variable_sens", "current_basal", "max_iob", "lgsThreshold"):
            if k in d2:
                val = _safe_float(d2.get(k))
                if k == "lgsThreshold":
                    d2[k] = val
                else:
                    d2[k] = val if val is not None else d2.get(k)
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


def _propagate_variable_sens_from_rt(rt_obj: Dict[str, Any], profile, autosens):
    if not isinstance(rt_obj, dict):
        return
    vs_rt = rt_obj.get("variable_sens") or rt_obj.get("variableSens")
    if vs_rt is None:
        return
    try:
        if profile is not None:
            profile.variable_sens = vs_rt
            setattr(profile, "_variable_sens_from_rt", True)
    except Exception:
        pass
    try:
        if autosens is not None:
            autosens.ratio = vs_rt
            setattr(autosens, "_variable_sens_from_rt", True)
    except Exception:
        pass


def build_inputs_from_block(block: List[Dict[str, Any]]) -> AutoIsfInputs:
    """
    Преобразует список объектов AutoISF-блока из логов AAPS
    в корректный AutoIsfInputs (core.autoisf_structs).
    """
    try:
        gs_obj = _find_first(block, "GlucoseStatusAutoIsf")
        ct_obj = _find_first(block, "CurrentTemp")
        rt_obj = _find_first(block, "RT")

        algorithm = rt_obj.get("algorithm") if isinstance(rt_obj, dict) else None
        algo_marker = {"algorithm": algorithm}

        profile_obj = (
            rt_obj.get("profile") if isinstance(rt_obj, dict) else None
        ) or _find_first(block, "OapsProfileAutoIsf")

        autosens_obj = (
            rt_obj.get("autosens") if isinstance(rt_obj, dict) else None
        ) or _find_first(block, "AutosensResult")

        meal_obj = (
            rt_obj.get("mealData") if isinstance(rt_obj, dict) else None
        ) or _find_first(block, "MealData")

        iob_objs = [
            o for o in block if isinstance(o, dict) and o.get("__type__") == "IobTotal"
        ]

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
        except Exception:
            profile = None

        try:
            autosens = _to_autosens(autosens_obj)
        except Exception:
            autosens = None

        _propagate_variable_sens_from_rt(rt_obj, profile, autosens)

        try:
            meal = _to_meal(meal_obj)
        except Exception:
            meal = None

        iob_array: List[IobTotal] = []
        for o in iob_objs:
            try:
                iob_array.append(_to_iob(o))
            except Exception:
                continue

        return AutoIsfInputs(
            glucose_status=gs,
            current_temp=ct,
            iob_data_array=iob_array,
            profile=profile,
            autosens=autosens,
            meal=meal,
            rt=rt_obj if isinstance(rt_obj, dict) else {},
            raw_block=[algo_marker] + block,
        )

    except Exception as exc:
        try:
            cache_dir = Path(__file__).resolve().parents[2] / "data" / "cache"
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

# ---------------------------------------------------------
#  Генерация inputs_before_algo_block_* из логов AAPS
# ---------------------------------------------------------


def build_inputs_from_logs(
    logs_dir: str = "data/logs",
    out_dir: str = "data/cache"
):
    """
    Загружает логи AAPS, выделяет AutoISF-блоки и сохраняет
    inputs_before_algo_block_*.json в data/cache/.
    Логика выделения блоков полностью совпадает с compare_runner.
    """

    logs_path = Path(logs_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Ищем .json, .log, .zip
    files = sorted(
        list(logs_path.rglob("*.json")) +
        list(logs_path.rglob("*.log")) +
        list(logs_path.rglob("*.zip"))
    )

    if not files:
        print(f"⚠ Нет логов в {logs_path}")
        return

    counter = 1

    for f in files:
        print(f"📄 Чтение {f.name}...")
        try:
            parsed = load_logs(f)
        except Exception as e:
            print(f"❌ Ошибка чтения {f}: {e}")
            continue

        # --- ЛОГИКА ВЫДЕЛЕНИЯ БЛОКОВ (как в compare_runner) ---
        blocks = []
        i = 0
        n = len(parsed)

        while i < n:
            obj = parsed[i]
            if isinstance(obj, dict) and obj.get("__type__") == "GlucoseStatusAutoIsf":
                block = [obj]
                j = i + 1
                while j < n:
                    block.append(parsed[j])
                    if isinstance(parsed[j], dict) and parsed[j].get("__type__") == "RT":
                        break
                    j += 1
                blocks.append(block)
                i = j + 1
            else:
                i += 1

        print(f"  → найдено {len(blocks)} AutoISF-блоков")

        # --- СОХРАНЕНИЕ ---
        for block in blocks:
            try:
                inputs = build_inputs_from_block(block)
                out_file = out_path / f"inputs_before_algo_block_{counter:05d}.json"
                with out_file.open("w", encoding="utf-8") as fp:
                    json.dump(inputs.to_dict(), fp, ensure_ascii=False, indent=2)
                counter += 1
            except Exception as e:
                print(f"❌ Ошибка обработки блока: {e}")

    print(f"✔ Создано {counter-1} файлов inputs_before_algo_block_*")
