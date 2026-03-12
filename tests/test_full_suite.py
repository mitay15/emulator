# tests/test_full_suite.py
import pytest


@pytest.mark.smoke
def test_smoke_compare_pipeline():
    from aaps_emulator.runner.compare_runner import compare_logs

    # прогоняем хотя бы один лог (или дефолтный data/logs)
    res = compare_logs(return_stats=True)
    assert res["total_blocks"] > 0


@pytest.mark.smoke
def test_smoke_single_block(all_blocks):
    from aaps_emulator.core.autoisf_pipeline import run_autoisf_pipeline

    path, inputs, expected, block_index = all_blocks[0]
    variable_sens, pred, dosing = run_autoisf_pipeline(inputs)

    assert variable_sens is not None
    assert getattr(pred, "eventual_bg", None) is not None
