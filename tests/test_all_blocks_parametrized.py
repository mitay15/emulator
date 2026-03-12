# tests/test_all_blocks_parametrized.py
import json
from pathlib import Path

import pytest

from aaps_emulator.core.autoisf_pipeline import run_autoisf_pipeline
from aaps_emulator.core.autoisf_structs import AutoIsfInputs

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

    if "variable_sens" in expected:
        assert (
            pytest.approx(variable_sens, rel=1e-3) == expected["variable_sens"]
        ), f"Block {block_index}: variable_sens mismatch"

    if "eventualBG" in expected:
        # PredictionsResult uses eventual_bg
        assert (
            pytest.approx(pred.eventual_bg, rel=1e-3) == expected["eventualBG"]
        ), f"Block {block_index}: eventualBG mismatch"
