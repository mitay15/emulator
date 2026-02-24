import re

from aaps_emulator.parsing.utils import clean_num


def parse_rt(rt_line):
    def get(name):
        m = re.search(rf"{name}=([0-9.\-E]+)", rt_line)
        return clean_num(m.group(1).rstrip(",")) if m else None

    return {
        "bg": get("bg"),
        "tick": get("tick"),
        "eventualBG": get("eventualBG"),
        "targetBG": get("targetBG"),
        "insulinReq": get("insulinReq"),
        "duration": int(get("duration") or 0),
        "rate": get("rate"),
        "iob": get("IOB"),
        "variable_sens": get("variable_sens"),
    }

def normalize_rt(rt_obj):
    """
    Normalize RT input (string or dict) to a dict with snake_case keys and
    BG values in mmol/L where applicable.

    Returned keys (when available):
      - bg (float, mmol/L)
      - tick
      - eventual_bg (float, mmol/L)
      - target_bg (float, mmol/L)
      - insulin_req (float)
      - duration (int, minutes)
      - rate (float, U/h)
      - iob (float)
      - variable_sens (float)  # if present, not converted
      - _raw_text (str)
    """
    # If input is already a dict, start from it; else parse the line
    parsed = {}
    if rt_obj is None:
        return parsed

    if isinstance(rt_obj, dict):
        parsed.update(rt_obj)
        parsed["_raw_text"] = " ".join(str(v) for v in rt_obj.values()).lower()
    else:
        # use existing parse_rt to extract basic numeric fields from a string
        parsed.update(parse_rt(str(rt_obj)))
        parsed["_raw_text"] = str(rt_obj).lower()

    out: dict = {}

    # key mapping from various possible names to canonical snake_case
    key_map = {
        "bg": "bg",
        "tick": "tick",
        "eventualBG": "eventual_bg",
        "eventual_bg": "eventual_bg",
        "eventual": "eventual_bg",
        "targetBG": "target_bg",
        "target_bg": "target_bg",
        "insulinReq": "insulin_req",
        "insulin_req": "insulin_req",
        "duration": "duration",
        "dur": "duration",
        "rate": "rate",
        "deliveryRate": "rate",
        "IOB": "iob",
        "iob": "iob",
        "variable_sens": "variable_sens",
        "variableSens": "variable_sens",
        "sensitivityRatio": "sensitivity_ratio",
        "sensitivity_ratio": "sensitivity_ratio",
    }

    # map keys
    for k, v in parsed.items():
        nk = key_map.get(k, k)
        out[nk] = v

    # ensure _raw_text present
    out["_raw_text"] = out.get("_raw_text", parsed.get("_raw_text", ""))

    # helper to normalize BG-like fields (convert mg/dL -> mmol/L if value > 30)
    def _norm_bg(val):
        if val is None:
            return None
        try:
            vf = float(val)
        except Exception:
            return None
        # heuristic: values > 30 likely mg/dL
        if vf > 30:
            return vf / 18.0
        return vf

    for bg_key in ("bg", "eventual_bg", "target_bg"):
        if bg_key in out:
            out[bg_key] = _norm_bg(out.get(bg_key))

    # numeric coercions
    try:
        if "duration" in out and out.get("duration") is not None:
            out["duration"] = int(float(out["duration"]))
    except Exception:
        out["duration"] = 0

    try:
        if "rate" in out and out.get("rate") is not None:
            out["rate"] = float(out["rate"])
    except Exception:
        out["rate"] = None

    try:
        if "insulin_req" in out and out.get("insulin_req") is not None:
            out["insulin_req"] = float(out["insulin_req"])
    except Exception:
        out["insulin_req"] = None

    try:
        if "iob" in out and out.get("iob") is not None:
            out["iob"] = float(out["iob"])
    except Exception:
        out["iob"] = None

    # sensitivity fields: keep as float if present (do not convert units)
    try:
        if "variable_sens" in out and out.get("variable_sens") is not None:
            out["variable_sens"] = float(out["variable_sens"])
    except Exception:
        out["variable_sens"] = None

    try:
        if "sensitivity_ratio" in out and out.get("sensitivity_ratio") is not None:
            out["sensitivity_ratio"] = float(out["sensitivity_ratio"])
    except Exception:
        out["sensitivity_ratio"] = None

    return out
