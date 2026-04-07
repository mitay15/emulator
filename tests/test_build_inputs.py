# tests/test_build_inputs.py

from aaps_emulator.runner.build_inputs import build_inputs


def test_build_inputs_minimal():
    """
    Проверяем, что build_inputs принимает минимальный словарь
    и возвращает корректную структуру AutoIsfInputs.
    """
    raw = {
        "glucose_status": {"glucose": 120, "delta": 1, "date": 1700000000000},
        "iob_data_array": [],
        "profile": {"current_basal": 1.0, "sens": 50, "carb_ratio": 10},
        "autosens": {"ratio": 1.0},
        "meal": {"mealCOB": 0, "carbs": 0},
    }

    inputs = build_inputs(raw)

    assert inputs is not None
    assert hasattr(inputs, "glucose_status")
    assert hasattr(inputs, "profile")
    assert hasattr(inputs, "autosens")
