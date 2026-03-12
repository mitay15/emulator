# tests/test_single_block_from_log.py
import json
from pathlib import Path

import pytest

from aaps_emulator.core.autoisf_structs import AutoIsfInputs
from aaps_emulator.core.autoisf_pipeline import run_autoisf_pipeline


CACHE_DIR = Path("data/cache")


@pytest.mark.integration
def test_single_block_from_cache():
    # Ищем любые блоки в кэше
    paths = sorted(CACHE_DIR.glob("inputs_before_algo_block_*.json"))
    assert paths, "В data/cache/ нет ни одного файла inputs_before_algo_block_*.json"

    # Берём первый доступный блок
    path = paths[0]

    raw = json.loads(path.read_text(encoding="utf-8"))

    # Данные могут быть в raw['inputs'] или на верхнем уровне
    inputs_raw = raw.get("inputs", raw)
    if not isinstance(inputs_raw, dict):
        raise TypeError(f"inputs_raw must be dict, got {type(inputs_raw)}")

    expected = raw.get("aaps", {})

    inputs = AutoIsfInputs(
        glucose_status=inputs_raw.get("glucose_status"),
        current_temp=inputs_raw.get("current_temp"),
        iob_data_array=inputs_raw.get("iob_data_array", []),
        profile=inputs_raw.get("profile"),
        autosens=inputs_raw.get("autosens"),
        meal=inputs_raw.get("meal"),
        rt=None,
        raw_block=raw,
    )

    # run_autoisf_pipeline returns (variable_sens, pred, dosing)
    variable_sens, pred, dosing = run_autoisf_pipeline(inputs)

    # Проверяем только те поля, которые реально есть в expected
    if "variable_sens" in expected:
        assert pytest.approx(variable_sens, rel=1e-3) == expected["variable_sens"]

    if "eventualBG" in expected:
        assert pytest.approx(pred.eventual_bg, rel=1e-3) == expected["eventualBG"]
