# tests/test_auto_ga_v3.py
from aaps_emulator.optimizer.genetic_optimizer import optimize_profile, OptimizationResult


def test_auto_ga_v3_smoke():
    """
    Smoke‑тест Auto‑GA v3: проверяем, что оптимизация запускается
    на минимальных данных и возвращает OptimizationResult.
    """

    # Минимальный набор блоков: список кортежей (start_ts, end_ts, block_data)
    blocks = [
        (0, 1000, [{"dummy": True}])
    ]

    base_profile = {
        "sens": 50,
        "carb_ratio": 10,
        "current_basal": 1.0,
    }

    override_profile = {}

    result = optimize_profile(
        blocks=blocks,
        base_profile=base_profile,
        override_profile=override_profile,
        generations=1,          # минимально
        population_size=4,      # минимально
        elitism=1,
        auto_mode=False,        # без Auto‑GA v3 адаптаций
    )

    assert isinstance(result, OptimizationResult)
    assert result.optimized_profile is not None
    assert len(result.history) >= 1
