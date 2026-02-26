import re
from re import Match
from typing import Any


def parse_rt_to_dict(rt_obj: Any) -> dict[str, Any]:
    """
    Преобразует RT-объект (dict или строку) в словарь со значениями float, где возможно.
    Добавляет ключ '_raw_text' — нижний регистр всей строки.
    """
    parsed: dict[str, Any] = {}

    if rt_obj is None:
        return parsed

    # Если это dict — копируем как есть
    if isinstance(rt_obj, dict):
        parsed.update(rt_obj)
        parsed["_raw_text"] = " ".join(str(v) for v in rt_obj.values()).lower()
        return parsed

    # Иначе — строка
    s = str(rt_obj)
    parsed["_raw_text"] = s.lower()

    # key=value
    for m in re.finditer(r"([A-Za-z_]+)\s*=\s*([0-9]+(?:[.,][0-9]+)?)", s):
        key = m.group(1)
        val = float(m.group(2).replace(",", "."))
        parsed[key] = val

    # key: value
    for m in re.finditer(r"([A-Za-z_]+)\s*:\s*([0-9]+(?:[.,][0-9]+)?)", s):
        key = m.group(1)
        val = float(m.group(2).replace(",", "."))
        parsed[key] = val

    # Eventual BG 13,4
    m_eventual: Match[str] | None = re.search(
        r"eventual\s*bg\s*([0-9]+(?:[.,][0-9]+)?)",
        s,
        flags=re.IGNORECASE,
    )
    if m_eventual:
        parsed["eventualBG"] = float(m_eventual.group(1).replace(",", "."))

    return parsed


def extract_lowtemp_rate(parsed_rt: dict[str, Any]) -> float | None:
    """
    Извлекает low-temp rate из текста RT.
    Возвращает float или None.
    """
    txt_raw = parsed_rt.get("_raw_text", "")
    txt = str(txt_raw).lower()

    if not txt:
        return None

    # temp 0,10 < 1,56U/hr
    m = re.search(r"<\s*([0-9]+(?:[.,][0-9]+)?)\s*u?/?h", txt)
    if m:
        return float(m.group(1).replace(",", "."))

    # low temp of 0.46U/h
    m = re.search(r"low\s*temp(?:\s*of)?\s*([0-9]+(?:[.,][0-9]+)?)\s*u?/?h", txt)
    if m:
        return float(m.group(1).replace(",", "."))

    # fallback: любое число перед U/h
    m = re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*u?/?h", txt)
    if m:
        return float(m.group(1).replace(",", "."))

    return None
