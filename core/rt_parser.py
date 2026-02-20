import re
from typing import Any, Dict, Optional

def parse_rt_to_dict(rt_obj: Any) -> Dict:
    """
    Универсальный парсер RT-строк AAPS.
    Понимает:
    - key=value
    - key: value
    - key value
    - eventualBG=244.0
    - Eventual BG 13,4
    - temp 0,10 < 1,56U/hr
    - low temp of 0.46U/h
    """
    parsed = {}

    if rt_obj is None:
        return parsed

    # Если это словарь — просто копируем
    if isinstance(rt_obj, dict):
        parsed.update(rt_obj)
        parsed["_raw_text"] = " ".join(str(v) for v in rt_obj.values()).lower()
        return parsed

    # Преобразуем в строку
    s = str(rt_obj)
    parsed["_raw_text"] = s.lower()

    # 1) key=value
    for m in re.finditer(r'([A-Za-z_]+)\s*=\s*([0-9]+(?:[.,][0-9]+)?)', s):
        parsed[m.group(1)] = float(m.group(2).replace(",", "."))

    # 2) key: value
    for m in re.finditer(r'([A-Za-z_]+)\s*:\s*([0-9]+(?:[.,][0-9]+)?)', s):
        parsed[m.group(1)] = float(m.group(2).replace(",", "."))

    # 3) Eventual BG 13,4
    m = re.search(r'eventual\s*bg\s*([0-9]+(?:[.,][0-9]+)?)', s, re.IGNORECASE)
    if m:
        parsed["eventualBG"] = float(m.group(1).replace(",", "."))

    return parsed


def extract_lowtemp_rate(parsed_rt: Dict) -> Optional[float]:
    """
    Извлекает low-temp rate из любых строк AAPS.
    """
    txt = parsed_rt.get("_raw_text", "")
    if not txt:
        return None

    # temp 0,10 < 1,56U/hr
    m = re.search(r'<\s*([0-9]+(?:[.,][0-9]+)?)\s*u?/?h', txt)
    if m:
        return float(m.group(1).replace(",", "."))

    # low temp of 0.46U/h
    m = re.search(r'low\s*temp(?:\s*of)?\s*([0-9]+(?:[.,][0-9]+)?)\s*u?/?h', txt)
    if m:
        return float(m.group(1).replace(",", "."))

    # fallback: любое число перед U/h
    m = re.search(r'([0-9]+(?:[.,][0-9]+)?)\s*u?/?h', txt)
    if m:
        return float(m.group(1).replace(",", "."))

    return None
