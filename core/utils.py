# aaps_emulator/core/utils.py
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation
import math

def _to_number_safe(v):
    """Попытка привести строку/число к float; возвращает None если не получилось."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        # заменить запятую на точку
        s = s.replace(",", ".")
        try:
            return float(s)
        except Exception:
            # попробуем Decimal (для экспоненциальной нотации Decimal тоже работает)
            try:
                return float(Decimal(s))
            except Exception:
                return None
    return None

def round_half_even(value: float, digits: int = 1) -> float:
    """
    BigDecimal HALF_EVEN compatible rounding used by Kotlin BigDecimal.
    Returns float or original value if not finite.
    """
    try:
        if value is None:
            return value
        # безопасно привести строковые представления
        vnum = _to_number_safe(value)
        if vnum is None:
            return value
        if not math.isfinite(vnum):
            return value
        q = Decimal(str(vnum)).quantize(Decimal(10) ** -digits, rounding=ROUND_HALF_EVEN)
        return float(q)
    except (InvalidOperation, TypeError):
        # последний шанс: попытаться вернуть float, если возможно
        try:
            v2 = _to_number_safe(value)
            return float(v2) if v2 is not None else value
        except Exception:
            return value
