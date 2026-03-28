# aaps_emulator/visual/utils.py
from __future__ import annotations
from datetime import datetime
from typing import Iterable, List, Tuple, Optional

def to_datetime(x) -> Optional[datetime]:
    if x is None:
        return None
    if isinstance(x, datetime):
        return x
    try:
        if isinstance(x, (int, float)):
            return datetime.fromtimestamp(int(x))
        return datetime.fromisoformat(str(x))
    except Exception:
        return None

def rmse(a: Iterable[float], b: Iterable[float]) -> Optional[float]:
    """Compute RMSE for pairs where both values are not None. Return None if no pairs."""
    s = 0.0
    n = 0
    for x, y in zip(a, b):
        if x is None or y is None:
            continue
        try:
            dx = float(x) - float(y)
        except Exception:
            continue
        s += dx * dx
        n += 1
    if n == 0:
        return None
    return (s / n) ** 0.5

def decimate_series(xs: List, ys: List, max_points: int = 1000) -> Tuple[List, List]:
    """
    Reduce number of points to at most max_points.
    Uses simple binning + mean aggregation to preserve trends.
    """
    if len(xs) <= max_points:
        return xs, ys
    import math
    step = math.ceil(len(xs) / max_points)
    xs_out, ys_out = [], []
    for i in range(0, len(xs), step):
        chunk_x = xs[i : i + step]
        chunk_y = [v for v in ys[i : i + step] if v is not None]
        if not chunk_x:
            continue
        # take middle timestamp for x
        mid_x = chunk_x[len(chunk_x) // 2]
        if chunk_y:
            mean_y = sum(chunk_y) / len(chunk_y)
        else:
            mean_y = None
        xs_out.append(mid_x)
        ys_out.append(mean_y)
    return xs_out, ys_out
