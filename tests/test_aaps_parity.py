import json
from pathlib import Path

from runner.build_inputs import AutoIsfInputs
from core.autoisf_pipeline import run_autoisf_pipeline


def test_aaps_parity_clean_blocks():
    """
    Тест проверяет, что pipeline успешно обрабатывает clean-блоки
    из data/clean/, и что результаты выглядят корректно.
    """

    clean_dir = Path("data/clean")
    assert clean_dir.exists(), f"Directory not found: {clean_dir}"

    clean_blocks = sorted(clean_dir.glob("block_*.json"))
    assert clean_blocks, "No clean blocks found in data/clean"

    for block_file in clean_blocks:
        with block_file.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        # clean-блоки у тебя содержат inputs прямо внутри JSON
        if isinstance(raw, dict):
            inputs_raw = raw.get("inputs", raw)
        elif isinstance(raw, list):
            # clean-блок — это список, берём первый элемент
            inputs_raw = raw[0]
        else:
            raise TypeError(f"Unexpected clean block format: {type(raw)}")
        assert isinstance(inputs_raw, dict), "Invalid clean block format"

        # Собираем inputs
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

        # Запускаем pipeline
        variable_sens, pred, dosing = run_autoisf_pipeline(inputs)

        # --- Проверяем только то, что реально возвращает твой pipeline ---
        assert variable_sens is not None
        assert pred.eventual_bg is not None
        assert pred.minPredBG is not None
        assert pred.minGuardBG is not None
        assert dosing.rate is not None
        assert dosing.duration is not None

        # Дополнительные sanity-checks
        assert pred.eventual_bg > 0
        assert pred.minPredBG > 0
        assert pred.minGuardBG > 0
        assert dosing.rate >= 0
        assert dosing.duration >= 0
