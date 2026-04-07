# tests/test_auto_ga_v3.py
import pytest

from aaps_emulator.optimizer.genetic_optimizer import run_optimizer


@pytest.mark.smoke
def test_auto_ga_v3_smoke():
    """
    Минимальный smoke‑тест: проверяем, что оптимизатор запускается,
    проходит несколько поколений и возвращает валидный результат.
    """
    result = run_optimizer(
        max_generations=3,
        population_size=10,
        elitism=2,
    )

    assert result is not None
    assert hasattr(result, "best_fitness")
    assert result.best_fitness is not None
    assert result.best_fitness >= 0
