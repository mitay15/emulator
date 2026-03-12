# tests/conftest.py
import json
from pathlib import Path
import pytest

from aaps_emulator.core.autoisf_structs import (
    AutoIsfInputs,
    GlucoseStatusAutoIsf,
    OapsProfileAutoIsf,
    AutosensResult,
    MealData,
    IobTotal,
    TempBasal,
)

CACHE_DIR = Path("data/cache")


def _dc(cls, value):
    if value is None or isinstance(value, cls):
        return value
    if isinstance(value, dict):
        try:
            return cls(**value)
        except Exception:
            # fallback: try to construct with minimal args
            return cls()
    return value


def _inputs_from_cache_dict(inputs_raw: dict) -> AutoIsfInputs:
    """
    Build AutoIsfInputs from cached dict produced by runner dumps.
    """
    return AutoIsfInputs(
        glucose_status=_dc(GlucoseStatusAutoIsf, inputs_raw.get("glucose_status")),
        current_temp=_dc(TempBasal, inputs_raw.get("current_temp")),
        iob_data_array=[_dc(IobTotal, x) for x in inputs_raw.get("iob_data_array", [])],
        profile=_dc(OapsProfileAutoIsf, inputs_raw.get("profile")),
        autosens=_dc(AutosensResult, inputs_raw.get("autosens")),
        meal=_dc(MealData, inputs_raw.get("meal")),
        rt=None,
        raw_block=inputs_raw,
    )


@pytest.fixture
def all_blocks():
    paths = sorted(CACHE_DIR.glob("inputs_before_algo_block_*.json"))
    assert paths, "В data/cache/ нет ни одного файла inputs_before_algo_block_*.json"

    blocks = []
    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))

        inputs_raw = raw.get("inputs", raw)
        if not isinstance(inputs_raw, dict):
            raise TypeError(f"inputs_raw must be dict, got {type(inputs_raw)}")

        expected = raw.get("aaps", {})
        inputs = _inputs_from_cache_dict(inputs_raw)
        block_index = raw.get("block_index", raw.get("index"))

        blocks.append((path, inputs, expected, block_index))

    return blocks
