# tests/test_compare_runner.py
import pytest

from aaps_emulator.runner.compare_runner import compare_logs


@pytest.mark.smoke
def test_compare_runner_smoke():
    """
    Проверяем, что compare_logs запускается и возвращает статистику.
    """
    stats = compare_logs(return_stats=True)

    assert isinstance(stats, dict)
    assert "total_blocks" in stats
    assert stats["total_blocks"] >= 0
