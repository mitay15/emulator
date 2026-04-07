# aaps_emulator/optimizer/population.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple
import random

from .utils import normalize_param, extract_profile_params


OPTIMIZED_KEYS = [
    "sens",
    "carb_ratio",
    "autoISF_min",
    "autoISF_max",
    "bgAccel_ISF_weight",
    "bgBrake_ISF_weight",
    "pp_ISF_weight",
    "dura_ISF_weight",
    "lower_ISFrange_weight",
    "higher_ISFrange_weight",
    "autosens_min",
    "autosens_max",
    "smb_delivery_ratio",
    "target_bg",
]


def build_param_ranges(base_profile: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
    ranges: Dict[str, Tuple[float, float]] = {}
    numeric = extract_profile_params(base_profile, OPTIMIZED_KEYS)

    for k, base in numeric.items():
        if k == "target_bg":
            lo, hi = normalize_param(base, base, factor=0.2)
        elif k in ("autosens_min", "autosens_max"):
            lo, hi = normalize_param(base, base, factor=0.2)
        else:
            # расширенный диапазон, чтобы GA реально двигал параметры
            lo, hi = normalize_param(base, base, factor=0.5)
        ranges[k] = (lo, hi)

    return ranges


def random_individual(ranges: Dict[str, Tuple[float, float]]) -> Dict[str, float]:
    indiv: Dict[str, float] = {}
    for k, (lo, hi) in ranges.items():
        indiv[k] = random.uniform(lo, hi)
    return indiv


def initial_population(
    base_profile: Dict[str, Any],
    pop_size: int,
) -> Tuple[List[Dict[str, float]], Dict[str, Tuple[float, float]]]:
    ranges = build_param_ranges(base_profile)
    population: List[Dict[str, float]] = []

    # включаем базовый профиль как одну особь
    base_numeric = extract_profile_params(base_profile, list(ranges.keys()))
    population.append(base_numeric)

    while len(population) < pop_size:
        population.append(random_individual(ranges))

    return population, ranges
