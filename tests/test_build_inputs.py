# tests/test_build_inputs.py
from aaps_emulator.runner.build_inputs import build_inputs_from_block
from aaps_emulator.core.autoisf_structs import AutoIsfInputs


def test_build_inputs_from_block_minimal():
    block = [
        {"__type__": "GlucoseStatusAutoIsf", "glucose": 120, "delta": 1, "date": 1700000000000},
        {"__type__": "OapsProfileAutoIsf", "current_basal": 1.0, "sens": 50, "carb_ratio": 10},
        {"__type__": "AutosensResult", "ratio": 1.0},
        {"__type__": "MealData", "carbs": 0, "mealCOB": 0},
    ]

    inputs = build_inputs_from_block(block)

    assert isinstance(inputs, AutoIsfInputs)
    assert inputs.glucose_status is not None
    assert inputs.profile is not None
    assert inputs.autosens is not None
    assert inputs.meal is not None
