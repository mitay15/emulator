# aaps_emulator/optimizer/genetic_optimizer.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional, Callable
import random
from multiprocessing import Pool, cpu_count

from .population import initial_population
from .crossover import mixed_crossover
from .mutation import mutate_individual
from .fitness_functions import evaluate_profile_fitness
from .utils import merge_profiles, diff_profiles


class OptimizationHistoryEntry:
    def __init__(self, generation: int, best_fitness: float, best_profile: Dict[str, float]):
        self.generation = generation
        self.best_fitness = best_fitness
        self.best_profile = dict(best_profile)


class OptimizationResult:
    def __init__(
        self,
        base_profile: Dict[str, Any],
        optimized_profile: Dict[str, Any],
        history: List[OptimizationHistoryEntry],
    ):
        self.base_profile = base_profile
        self.optimized_profile = optimized_profile
        self.history = history

    def profile_diff(self) -> Dict[str, Tuple[Any, Any]]:
        return diff_profiles(self.base_profile, self.optimized_profile)


def tournament_selection(
    population: List[Dict[str, float]],
    fitnesses: List[float],
    k: int = 3,
) -> Dict[str, float]:
    idxs = random.sample(range(len(population)), k)
    best_idx = min(idxs, key=lambda i: fitnesses[i])
    return dict(population[best_idx])


def _fitness_wrapper(args):
    indiv, blocks, full_base_profile, start_ts, end_ts = args
    return evaluate_profile_fitness(
        blocks,
        {**full_base_profile, **indiv},
        start_ts,
        end_ts,
    )


def _population_diversity(population: List[Dict[str, float]]) -> float:
    """
    Простейшая оценка разнообразия популяции:
    среднее стандартное отклонение по параметрам.
    """
    if not population:
        return 0.0
    keys = list(population[0].keys())
    if not keys:
        return 0.0

    vals_per_key: Dict[str, List[float]] = {k: [] for k in keys}
    for indiv in population:
        for k in keys:
            v = indiv.get(k)
            if isinstance(v, (int, float)):
                vals_per_key[k].append(float(v))

    import math
    stds = []
    for k, vals in vals_per_key.items():
        if len(vals) < 2:
            continue
        m = sum(vals) / len(vals)
        var = sum((x - m) ** 2 for x in vals) / len(vals)
        stds.append(math.sqrt(var))

    if not stds:
        return 0.0
    return sum(stds) / len(stds)


def optimize_profile(
    blocks: List[Tuple[int, int, List[dict]]],
    base_profile: Dict[str, Any],
    override_profile: Dict[str, Any],
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    population_size: int = 80,
    generations: int = 40,
    elitism: int = 2,
    auto_mode: bool = False,
    progress_callback: Optional[Callable[[int, float, Optional[str]], None]] = None,
) -> OptimizationResult:
    """
    Главная функция оптимизации профиля.
    auto_mode: включает Auto‑GA v3 (адаптивные диапазоны, мутация, элитизм, размер популяции, early stopping).
    """
    full_base_profile = merge_profiles(base_profile, override_profile)

    population, ranges = initial_population(full_base_profile, population_size)

    history: List[OptimizationHistoryEntry] = []

    best_overall: Optional[float] = None
    prev_best: Optional[float] = None
    no_improve_count = 0

    # базовые параметры Auto‑GA
    base_mutation_rate = 0.2
    mutation_rate = base_mutation_rate
    min_mutation_rate = 0.05
    max_mutation_rate = 0.5

    min_elitism = 1
    max_elitism = max(3, elitism)

    base_pop = population_size
    min_pop = max(30, base_pop // 2)
    max_pop = max(base_pop, base_pop * 2)

    patience = 20
    min_improvement = 0.01  # 1%

    for gen in range(generations):
        # --- оценка fitness ---
        with Pool(cpu_count()) as pool:
            fitnesses = pool.map(
                _fitness_wrapper,
                [
                    (indiv, blocks, full_base_profile, start_ts, end_ts)
                    for indiv in population
                ],
            )

        ranked = sorted(zip(population, fitnesses), key=lambda x: x[1])
        population = [p for p, f in ranked]
        fitnesses = [f for p, f in ranked]

        best_indiv = population[0]
        best_fit = fitnesses[0]

        history.append(OptimizationHistoryEntry(gen, best_fit, best_indiv))

        note: Optional[str] = None

        # --- трекинг улучшения ---
        if best_overall is None or best_fit < best_overall - min_improvement:
            best_overall = best_fit
            no_improve_count = 0
        else:
            no_improve_count += 1

        diversity = _population_diversity(population)

        if auto_mode:
            # 1) адаптивная мутация: прогресс → ослабляем, застой → усиливаем
            if prev_best is not None:
                if best_fit < prev_best - min_improvement:
                    mutation_rate = max(min_mutation_rate, mutation_rate * 0.9)
                else:
                    mutation_rate = min(max_mutation_rate, mutation_rate * 1.1)
            prev_best = best_fit

            # 2) адаптивный элитизм: при сильном шуме/разнообразии усиливаем, при стабильности уменьшаем
            if diversity > 0:  # есть смысл смотреть
                if no_improve_count > patience // 2:
                    elitism = min(max_elitism, elitism + 1)
                else:
                    elitism = max(min_elitism, elitism - 1)

            # 3) адаптивный размер популяции:
            #    если долго нет улучшения → расширяем популяцию,
            #    если улучшение стабильное → сужаем к базовому
            if no_improve_count > patience // 2:
                population_size = min(max_pop, int(population_size * 1.2))
            else:
                population_size = max(min_pop, int(population_size * 0.9))

            # 4) адаптивные диапазоны параметров
            for param, (low, high) in list(ranges.items()):
                if param not in best_indiv:
                    continue
                best_val = best_indiv[param]

                if low is None or high is None:
                    continue
                span = high - low
                if span <= 0:
                    continue

                # расширяем, если упёрлись в край
                if best_val <= low + 0.05 * span:
                    new_low = low - 0.1 * abs(low if low != 0 else 1.0)
                    ranges[param] = (new_low, high)

                if best_val >= high - 0.05 * span:
                    new_high = high + 0.1 * abs(high if high != 0 else 1.0)
                    ranges[param] = (low, new_high)

                # сужаем, если значение стабильно внутри диапазона
                low2, high2 = ranges[param]
                span2 = high2 - low2
                if span2 <= 0:
                    continue
                if (low2 + 0.3 * span2) < best_val < (high2 - 0.3 * span2):
                    new_low2 = best_val - 0.5 * (best_val - low2)
                    new_high2 = best_val + 0.5 * (high2 - best_val)
                    ranges[param] = (new_low2, new_high2)

            # 5) мягкий early stopping
            if no_improve_count >= patience:
                note = (
                    f"Auto‑GA v3: early stopping на поколении {gen} "
                    f"(нет улучшения {patience} поколений, "
                    f"mut={mutation_rate:.3f}, elitism={elitism}, pop={population_size}, div={diversity:.3f})"
                )
                if progress_callback is not None:
                    progress_callback(gen, best_fit, note)
                break

            note = (
                f"Auto‑GA v3: mut={mutation_rate:.3f}, elitism={elitism}, "
                f"pop={population_size}, div={diversity:.3f}, no_improve={no_improve_count}"
            )

        # --- callback прогресса ---
        if progress_callback is not None:
            progress_callback(gen, best_fit, note)

        # --- формирование нового поколения ---
        new_population: List[Dict[str, float]] = []

        # элитизм
        for i in range(min(elitism, len(population))):
            new_population.append(dict(population[i]))

        # селекция/кроссовер/мутация
        while len(new_population) < population_size:
            parent1 = tournament_selection(population, fitnesses, k=3)
            parent2 = tournament_selection(population, fitnesses, k=3)
            child1, child2 = mixed_crossover(parent1, parent2)
            child1 = mutate_individual(child1, ranges, base_mutation_rate=mutation_rate)
            child2 = mutate_individual(child2, ranges, base_mutation_rate=mutation_rate)
            new_population.append(child1)
            if len(new_population) < population_size:
                new_population.append(child2)

        population = new_population

    # финальный лучший (без multiprocessing)
    final_fitnesses = [
        evaluate_profile_fitness(blocks, {**full_base_profile, **indiv}, start_ts, end_ts)
        for indiv in population
    ]
    ranked = sorted(zip(population, final_fitnesses), key=lambda x: x[1])
    best_indiv = ranked[0][0]

    optimized_profile = dict(full_base_profile)
    optimized_profile.update(best_indiv)

    return OptimizationResult(
        base_profile=full_base_profile,
        optimized_profile=optimized_profile,
        history=history,
    )
