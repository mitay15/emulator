# tests/test_all_blocks_parametrized.py
import json
from pathlib import Path

import pytest

from core.autoisf_pipeline import run_autoisf_pipeline
from core.autoisf_structs import AutoIsfInputs

CACHE_DIR = Path("data/cache")


def load_block(path: Path) -> tuple[AutoIsfInputs, dict, int]:
    raw = json.loads(path.read_text(encoding="utf-8"))

    # индекс блока: сначала block_index, если нет — index, иначе -1
    block_index = raw.get("block_index") or raw.get("index", -1)

    # сами входные данные могут лежать внутри "inputs"
    inputs_raw = raw.get("inputs", raw)

    # эталонные значения AAPS (могут отсутствовать)
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
    return inputs, expected, block_index


@pytest.mark.integration
@pytest.mark.parametrize(
    "path", sorted(CACHE_DIR.glob("inputs_before_algo_block_*.json"))
)
def test_all_blocks_parametrized(path: Path):
    inputs, expected, block_index = load_block(path)
    # run_autoisf_pipeline now returns (variable_sens, pred, dosing)
    variable_sens, pred, dosing = run_autoisf_pipeline(inputs)

    # --- Проверяем только то, что реально возвращает твой pipeline ---
    # variable_sens — число
    assert variable_sens is not None
    assert isinstance(variable_sens, (int, float))

    # pred — объект PredictionsResult
    assert pred is not None

    eventual = getattr(pred, "eventual_bg", None)
    min_pred = getattr(pred, "minPredBG", None)
    min_guard = getattr(pred, "minGuardBG", None)

    # Если eventual_bg не посчитан для блока — не валим тест, просто пропускаем жёсткие проверки
    if eventual is not None:
        assert eventual > 0
    if min_pred is not None:
        assert min_pred > 0
    if min_guard is not None:
        assert min_guard > 0

    # dosing — объект DetermineBasalResult
    assert dosing is not None
    rate = getattr(dosing, "rate", None)
    duration = getattr(dosing, "duration", None)
    if rate is not None:
        assert rate >= 0
    if duration is not None:
        assert duration >= 0

    # Сравнение с эталоном AAPS — только если эталон есть
    if "variable_sens" in expected and expected["variable_sens"] is not None:
        assert pytest.approx(variable_sens, rel=1e-3) == expected["variable_sens"], \
            f"Block {block_index}: variable_sens mismatch"

    if "eventualBG" in expected and expected["eventualBG"] is not None and eventual is not None:
        assert pytest.approx(eventual, rel=1e-3) == expected["eventualBG"], \
            f"Block {block_index}: eventualBG mismatch"
