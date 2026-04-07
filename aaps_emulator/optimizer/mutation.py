# aaps_emulator/optimizer/mutation.py

from __future__ import annotations
from typing import Dict, Tuple
import random

from .utils import clamp


def mutate_individual(
    indiv: Dict[str, float],
    ranges: Dict[str, Tuple[float, float]],
    base_mutation_rate: float = 0.2,
) -> Dict[str, float]:
    """
    Адаптивная мутация:
    - базовая вероятность изменения параметра: base_mutation_rate
    - шаг мутации зависит от ширины диапазона
    """
    out = dict(indiv)

    for k, (lo, hi) in ranges.items():
        if random.random() < base_mutation_rate:
            span = hi - lo
            step = span * 0.1  # 10% диапазона
            delta = random.uniform(-step, step)
            out[k] = clamp(out[k] + delta, lo, hi)

    return out
