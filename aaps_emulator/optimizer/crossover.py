# aaps_emulator/optimizer/crossover.py
from __future__ import annotations
from typing import Dict, Tuple
import random


def uniform_crossover(
    parent1: Dict[str, float],
    parent2: Dict[str, float],
) -> Tuple[Dict[str, float], Dict[str, float]]:
    child1 = {}
    child2 = {}
    for k in parent1.keys():
        if random.random() < 0.5:
            child1[k] = parent1[k]
            child2[k] = parent2[k]
        else:
            child1[k] = parent2[k]
            child2[k] = parent1[k]
    return child1, child2


def one_point_crossover(
    parent1: Dict[str, float],
    parent2: Dict[str, float],
) -> Tuple[Dict[str, float], Dict[str, float]]:
    keys = list(parent1.keys())
    if len(keys) < 2:
        return dict(parent1), dict(parent2)

    point = random.randint(1, len(keys) - 1)
    child1 = {}
    child2 = {}
    for i, k in enumerate(keys):
        if i < point:
            child1[k] = parent1[k]
            child2[k] = parent2[k]
        else:
            child1[k] = parent2[k]
            child2[k] = parent1[k]
    return child1, child2


def mixed_crossover(
    parent1: Dict[str, float],
    parent2: Dict[str, float],
) -> Tuple[Dict[str, float], Dict[str, float]]:
    if random.random() < 0.5:
        return uniform_crossover(parent1, parent2)
    else:
        return one_point_crossover(parent1, parent2)
