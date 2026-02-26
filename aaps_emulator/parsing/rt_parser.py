import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _to_snake(key: str) -> str:
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
        except Exception as e:
            logger.debug("normalize_rt: non-numeric list element %r in %s (%s)", x, name, e)

    return out


def _maybe_convert_eventual(val: Any) -> Any:
    try:
        v = float(val)
        return v / 18.0 if v > 30 else v
    except Exception:
        return val


def normalize_rt(rt_raw: Any | None) -> dict[str, Any]:
    out: dict[str, Any] = {}

    # ---------------------- CASE 1: dict ----------------------
    if isinstance(rt_raw, dict):
        for k, v in rt_raw.items():
            out[_to_snake(k)] = v

        # convert eventual_bg
        if "eventual_bg" in out:
            out["eventual_bg"] = _maybe_convert_eventual(out["eventual_bg"])

        # numeric fields
        for num_key in (
            "rate",
            "duration",
            "insulin_req",
            "variable_sens",
            "target_bg",
            "bg",
            "units",
            "iob",
            "cob",
        ):
            if num_key in out:
                try:
                    if num_key == "duration":
                        out[num_key] = int(float(out[num_key]))
                    else:
                        out[num_key] = float(out[num_key])
                except Exception as e:
                    logger.debug("normalize_rt: failed to cast %s=%r (%s)", num_key, out.get(num_key), e)

        # convert target_bg mg/dL → mmol/L
        if "target_bg" in out:
            try:
                tg = float(out["target_bg"])
                out["target_bg"] = tg / 18.0 if tg > 30 else tg
            except Exception as e:
                logger.debug("normalize_rt: failed to normalize target_bg=%r (%s)", out.get("target_bg"), e)

        # ensure pred lists
        for pred_key in ("pred_cob", "pred_iob", "pred_uam", "pred_zt", "predictions"):
            if pred_key in out and not isinstance(out[pred_key], (list, tuple)):
                try:
                    out[pred_key] = list(out[pred_key])
                except Exception:
                    out[pred_key] = []

        # derive eventual_bg if missing
        if "eventual_bg" not in out:
            for pk in ("predictions", "pred_cob", "pred_iob", "pred_uam", "pred_zt"):
                vals = out.get(pk)
                if isinstance(vals, (list, tuple)) and vals:
                    try:
                        last = float(vals[-1])
                        out["eventual_bg"] = last / 18.0 if last > 30 else last
                        break
                    except Exception as e:
                        logger.debug("normalize_rt: failed to derive eventual_bg from %s (%s)", pk, e)

        # ensure keys exist
        out.setdefault("pred_cob", [])
        out.setdefault("pred_iob", [])
        out.setdefault("pred_uam", [])
        out.setdefault("pred_zt", [])

        return out

    # ---------------------- CASE 2: empty ----------------------
    if not rt_raw:
        return {}

    # ---------------------- CASE 3: string ----------------------
    if isinstance(rt_raw, str):
        s = rt_raw

        # timestamp
        m = re.search(r"timestamp\s*=\s*([0-9]+)", s)
        if m:
            try:
                out["timestamp"] = int(m.group(1))
            except Exception as e:
                logger.debug("normalize_rt: bad timestamp %r (%s)", m.group(1), e)

        # bg
        m = re.search(r"\bbg\s*=\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                bg = float(m.group(1).replace(",", "."))
                out["bg"] = bg / 18.0 if bg > 30 else bg
            except Exception as e:
                logger.debug("normalize_rt: failed to parse bg %r (%s)", m.group(1), e)

        # eventualBG
        m = re.search(r"eventual(?:BG|_bg)?\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                ev = float(m.group(1).replace(",", "."))
                out["eventual_bg"] = ev / 18.0 if ev > 30 else ev
            except Exception as e:
                logger.debug("normalize_rt: failed to parse eventualBG %r (%s)", m.group(1), e)

        # targetBG
        m = re.search(r"target(?:BG|_bg)?\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                tg = float(m.group(1).replace(",", "."))
                out["target_bg"] = tg / 18.0 if tg > 30 else tg
            except Exception as e:
                logger.debug("normalize_rt: failed to parse targetBG %r (%s)", m.group(1), e)

        # insulinReq
        m = re.search(r"insulinReq\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                out["insulin_req"] = float(m.group(1).replace(",", "."))
            except Exception as e:
                logger.debug("normalize_rt: failed to parse insulinReq %r (%s)", m.group(1), e)

        # rate
        m = re.search(r"\brate\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                out["rate"] = float(m.group(1).replace(",", "."))
            except Exception as e:
                logger.debug("normalize_rt: failed to parse rate %r (%s)", m.group(1), e)

        # duration
        m = re.search(r"\bduration\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                out["duration"] = int(float(m.group(1).replace(",", ".")))
            except Exception as e:
                logger.debug("normalize_rt: failed to parse duration %r (%s)", m.group(1), e)

        # units
        m = re.search(r"\bunits\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                out["units"] = float(m.group(1).replace(",", "."))
            except Exception as e:
                logger.debug("normalize_rt: failed to parse units %r (%s)", m.group(1), e)

        # variableSens
        m = re.search(r"variable(?:Sens|_sens)\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                out["variable_sens"] = float(m.group(1).replace(",", "."))
            except Exception as e:
                logger.debug("normalize_rt: failed to parse variable_sens %r (%s)", m.group(1), e)

        # COB / IOB numeric
        m = re.search(r"\bCOB\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                out["cob"] = float(m.group(1).replace(",", "."))
            except Exception as e:
                logger.debug("normalize_rt: failed to parse cob %r (%s)", m.group(1), e)

        m = re.search(r"\bIOB\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)", s, flags=re.IGNORECASE)
        if m:
            try:
                out["iob"] = float(m.group(1).replace(",", "."))
            except Exception as e:
                logger.debug("normalize_rt: failed to parse iob %r (%s)", m.group(1), e)

        # pred lists
        out["pred_iob"] = _parse_list_from_text("IOB", s)
        out["pred_cob"] = _parse_list_from_text("COB", s)
        out["pred_uam"] = _parse_list_from_text("UAM", s)
        out["pred_zt"] = _parse_list_from_text("ZT", s)

        preds = _parse_list_from_text("predBGs", s) or _parse_list_from_text("predictions", s)
        if preds:
            out["predictions"] = preds

        out.setdefault("pred_cob", [])
        out.setdefault("pred_iob", [])
        out.setdefault("pred_uam", [])
        out.setdefault("pred_zt", [])

        return out

    # ---------------------- fallback ----------------------
    return {}


def parse_rt_to_dict(rt: Any) -> dict[str, Any]:
    if isinstance(rt, dict):
        return normalize_rt(rt)
    if isinstance(rt, str):
        return normalize_rt(rt)
    return {}
