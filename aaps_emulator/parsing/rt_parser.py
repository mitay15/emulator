import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _to_snake(key: str) -> str:
    """
    Простая нормализация ключей из разных форматов в ожидаемый snake_case.
    """
    mapping = {
        "eventualBG": "eventual_bg",
        "eventualBg": "eventual_bg",
        "eventual_bg": "eventual_bg",
        "variableSens": "variable_sens",
        "variable_sens": "variable_sens",
        "insulinReq": "insulin_req",
        "insulin_req": "insulin_req",
        "targetBG": "target_bg",
        "target_bg": "target_bg",
        "predBGs": "predictions",
        "preds": "predictions",
        "predictions": "predictions",
        "COB": "pred_cob",
        "IOB": "pred_iob",
        "UAM": "pred_uam",
        "ZT": "pred_zt",
        "cob": "cob",
        "iob": "iob",
        "bg": "bg",
        "rate": "rate",
        "duration": "duration",
        "units": "units",
        "timestamp": "timestamp",
    }
    return mapping.get(key, key)


def _parse_list_from_text(name: str, text: str) -> list[float]:
    """
    Ищет в тексте выражения вида NAME=[1,2,3] или NAME=[1 2 3] и возвращает список float.
    Поиск нечувствителен к регистру.
    """
    pattern = rf"{re.escape(name)}\s*=\s*\[([0-9.,\s]+)\]"
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return []
    arr = m.group(1).replace(" ", "").split(",")
    out: list[float] = []
    for x in arr:
        if not x:
            continue
        try:
            out.append(float(x))
        except Exception:
            logger.debug("normalize_rt: non-numeric list element %r in %s", x, name)
    return out


def _maybe_convert_eventual(val: Any) -> Any:
    """
    Если eventual выглядит как число и >30 — считаем, что это mg/dL и конвертируем в mmol/L.
    Иначе возвращаем float или исходное значение.
    """
    try:
        v = float(val)
        if v > 30:
            return v / 18.0
        return v
    except Exception:
        return val


def normalize_rt(rt_raw: str | dict | None) -> dict:
    """
    Нормализует RT (строку или словарь) в словарь со snake_case ключами.
    Конвертирует eventualBG из mg/dL в mmol/L если значение > 30.
    Поддерживает парсинг строк вида:
      'eventualBG=144 duration=30 rate=0.5 insulinReq=0.2 variableSens=7'
    Возвращает словарь с ключами, ожидаемыми downstream кодом:
      eventual_bg, duration, rate, insulin_req, variable_sens,
      pred_cob, pred_iob, pred_uam, pred_zt, cob, iob, bg,
      timestamp, units
    """
    out: dict[str, Any] = {}

    # Если передан dict-like — нормализуем ключи и приведём числовые поля
    if isinstance(rt_raw, dict):
        for k, v in rt_raw.items():
            key = _to_snake(k)
            out[key] = v

        # Привести eventual_bg, если есть
        if "eventual_bg" in out:
            out["eventual_bg"] = _maybe_convert_eventual(out["eventual_bg"])

        # Привести числовые поля, если возможно
        for num_key in ("rate", "duration", "insulin_req", "variable_sens", "target_bg", "bg", "units", "iob", "cob"):
            if num_key in out:
                try:
                    if num_key == "duration":
                        out[num_key] = int(float(out[num_key]))
                    else:
                        out[num_key] = float(out[num_key])
                except Exception:
                    logger.debug("normalize_rt: failed to cast %s=%r", num_key, out.get(num_key))

        # Если target_bg присутствует и похоже на mg/dL (больше 30), конвертируем в mmol/L
        if "target_bg" in out:
            try:
                tg = float(out["target_bg"])
                if tg > 30:
                    out["target_bg"] = tg / 18.0
                else:
                    out["target_bg"] = tg
            except Exception:
                logger.debug("normalize_rt: failed to normalize target_bg=%r", out.get("target_bg"))

        # Нормализовать предсказания в списки
        for pred_key in ("pred_cob", "pred_iob", "pred_uam", "pred_zt", "predictions"):
            if pred_key in out and not isinstance(out[pred_key], (list, tuple)):
                try:
                    out[pred_key] = list(out[pred_key])
                except Exception:
                    out[pred_key] = []

        # Убедиться, что eventual_bg присутствует, если есть pred списки
        if "eventual_bg" not in out:
            # попытка извлечь из pred списков
            for pk in ("predictions", "pred_cob", "pred_iob", "pred_uam", "pred_zt"):
                vals = out.get(pk)
                if isinstance(vals, (list, tuple)) and len(vals) > 0:
                    try:
                        last = float(vals[-1])
                        out["eventual_bg"] = last / 18.0 if last > 30 else last
                        break
                    except Exception as e:
                        logger.debug("normalize_rt: failed to derive eventual_bg from %s: %s", pk, e)
                        continue

        # Гарантируем наличие пустых pred_* ключей для downstream
        out.setdefault("pred_cob", [])
        out.setdefault("pred_iob", [])
        out.setdefault("pred_uam", [])
        out.setdefault("pred_zt", [])

        return out

    # Если rt_raw пустой или None — вернуть пустой словарь
    if not rt_raw:
        return {}

    # Если строка — парсим ключ=значение
    if isinstance(rt_raw, str):
        s = rt_raw

        # timestamp
        m = re.search(r"timestamp\s*=\s*([0-9]+)", s)
        if m:
            try:
                out["timestamp"] = int(m.group(1))
            except Exception:
                logger.debug("normalize_rt: bad timestamp %r", m.group(1))

        # bg (mg/dL -> mmol/L if >30)
        m = re.search(r"\bbg\s*=\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                bg = float(m.group(1).replace(",", "."))
                out["bg"] = bg / 18.0 if bg > 30 else bg
            except Exception:
                logger.debug("normalize_rt: failed to parse bg %r", m.group(1))

        # eventualBG (various forms)
        m = re.search(r"eventual(?:BG|_bg)?\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                ev = float(m.group(1).replace(",", "."))
                out["eventual_bg"] = ev / 18.0 if ev > 30 else ev
            except Exception:
                logger.debug("normalize_rt: failed to parse eventualBG %r", m.group(1))

        # targetBG
        m = re.search(r"target(?:BG|_bg)?\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                tg = float(m.group(1).replace(",", "."))
                out["target_bg"] = tg / 18.0 if tg > 30 else tg
            except Exception:
                logger.debug("normalize_rt: failed to parse targetBG %r", m.group(1))

        # insulinReq
        m = re.search(r"insulinReq\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                out["insulin_req"] = float(m.group(1).replace(",", "."))
            except Exception:
                logger.debug("normalize_rt: failed to parse insulinReq %r", m.group(1))

        # rate
        m = re.search(r"\brate\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                out["rate"] = float(m.group(1).replace(",", "."))
            except Exception:
                logger.debug("normalize_rt: failed to parse rate %r", m.group(1))

        # duration
        m = re.search(r"\bduration\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                out["duration"] = int(float(m.group(1).replace(",", ".")))
            except Exception:
                logger.debug("normalize_rt: failed to parse duration %r", m.group(1))

        # units
        m = re.search(r"\bunits\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                out["units"] = float(m.group(1).replace(",", "."))
            except Exception:
                logger.debug("normalize_rt: failed to parse units %r", m.group(1))

        # variableSens (accept both variableSens and variable_sens)
        m = re.search(r"variable(?:Sens|_sens)\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                out["variable_sens"] = float(m.group(1).replace(",", "."))
            except Exception:
                logger.debug("normalize_rt: failed to parse variable_sens %r", m.group(1))

        # COB / IOB numeric single values (not lists)
        m = re.search(r"\bCOB\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                out["cob"] = float(m.group(1).replace(",", "."))
            except Exception:
                logger.debug("normalize_rt: failed to parse cob %r", m.group(1))

        m = re.search(r"\bIOB\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                out["iob"] = float(m.group(1).replace(",", "."))
            except Exception:
                logger.debug("normalize_rt: failed to parse iob %r", m.group(1))

        # pred lists: try to extract named lists (IOB=[...], COB=[...], UAM=[...], ZT=[...])
        out["pred_iob"] = _parse_list_from_text("IOB", s) or []
        out["pred_cob"] = _parse_list_from_text("COB", s) or []
        out["pred_uam"] = _parse_list_from_text("UAM", s) or []
        out["pred_zt"] = _parse_list_from_text("ZT", s) or []

        # If predictions exist under a generic predBGs or predictions key like predBGs=[...]
        preds = _parse_list_from_text("predBGs", s) or _parse_list_from_text("predictions", s)
        if preds:
            out.setdefault("predictions", preds)

        # Ensure keys exist for downstream code
        out.setdefault("pred_cob", [])
        out.setdefault("pred_iob", [])
        out.setdefault("pred_uam", [])
        out.setdefault("pred_zt", [])

        return out

    # Fallback: unknown type
    return {}


def parse_rt_to_dict(rt: Any) -> dict:
    """
    Возвращает нормализованный словарь RT, если rt — строка или dict.
    Иначе возвращает пустой dict.
    """
    if isinstance(rt, dict):
        return normalize_rt(rt)
    if isinstance(rt, str):
        return normalize_rt(rt)
    return {}
