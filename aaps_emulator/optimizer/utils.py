# aaps_emulator/optimizer/utils.py

from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
import math


# ============================================================
# BASIC HELPERS
# ============================================================

def clamp(value: float, min_val: float, max_val: float) -> float:
    """Ограничивает значение в диапазоне [min_val, max_val]."""
    if value is None:
        return min_val
    return max(min_val, min(max_val, value))


def safe_float(x: Any, default: float = None) -> Optional[float]:
    """Безопасное преобразование в float."""
    try:
        return float(x)
    except Exception:
        return default


def safe_int(x: Any, default: int = None) -> Optional[int]:
    """Безопасное преобразование в int."""
    try:
        return int(x)
    except Exception:
        return default


def normalize_param(value: float, base: float, factor: float = 0.5) -> Tuple[float, float]:
    """
    Возвращает диапазон для параметра:
    base ± (base * factor)
    """
    if base is None:
        return (0.0, 0.0)

    delta = abs(base * factor)
    return (base - delta, base + delta)


# ============================================================
# PROFILE HELPERS
# ============================================================

def merge_profiles(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Объединяет два профиля:
    - base: профиль из inputs_before_algo_block
    - override: изменения пользователя
    """
    out = dict(base)
    out.update(override)
    return out


def extract_profile_params(profile: Dict[str, Any], keys: List[str]) -> Dict[str, float]:
    """
    Извлекает только числовые параметры из профиля.
    """
    out = {}
    for k in keys:
        v = profile.get(k)
        if isinstance(v, (int, float)):
            out[k] = float(v)
    return out


# ============================================================
# DATE RANGE FILTERING
# ============================================================

def filter_blocks_by_date(
    blocks: List[Tuple[int, int, List[dict]]],
    start_ts: Optional[int],
    end_ts: Optional[int]
) -> List[Tuple[int, int, List[dict]]]:
    """
    Фильтрует блоки по диапазону дат.
    blocks: список (idx, timestamp, block_objs)
    start_ts, end_ts: UNIX ms timestamps
    """
    if start_ts is None and end_ts is None:
        return blocks

    out = []
    for idx, ts, block in blocks:
        if start_ts is not None and ts < start_ts:
            continue
        if end_ts is not None and ts > end_ts:
            continue
        out.append((idx, ts, block))

    return out


# ============================================================
# FITNESS HELPERS
# ============================================================

def rmse(a: List[float], b: List[float]) -> float:
    """
    Корень из средней квадратичной ошибки.
    """
    if not a or not b:
        return 999999.0

    s = 0.0
    n = 0
    for x, y in zip(a, b):
        if x is None or y is None:
            continue
        s += (x - y) ** 2
        n += 1

    if n == 0:
        return 999999.0

    return math.sqrt(s / n)


def mae(a: List[float], b: List[float]) -> float:
    """
    Средняя абсолютная ошибка.
    """
    if not a or not b:
        return 999999.0

    s = 0.0
    n = 0
    for x, y in zip(a, b):
        if x is None or y is None:
            continue
        s += abs(x - y)
        n += 1

    if n == 0:
        return 999999.0

    return s / n


# ============================================================
# LOGGING HELPERS
# ============================================================

def format_profile(profile: Dict[str, Any]) -> str:
    """Форматирует профиль в удобный текст."""
    lines = []
    for k, v in profile.items():
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


def diff_profiles(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
    """
    Возвращает словарь:
    param → (old_value, new_value)
    """
    out = {}
    for k in new.keys():
        old_v = old.get(k)
        new_v = new.get(k)
        if old_v != new_v:
            out[k] = (old_v, new_v)
    return out
