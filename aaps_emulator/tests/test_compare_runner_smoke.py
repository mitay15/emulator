from pathlib import Path
from aaps_emulator.analysis.compare_runner import run_compare_on_all_logs


def test_compare_runner_smoke(tmp_path):
    # Папка с ZIP‑логами
    logs_dir = Path("aaps_emulator/logs")

    # Запускаем сравнение на всех ZIP
    rows, blocks, inputs = run_compare_on_all_logs(logs_dir)

    # Проверяем, что что‑то найдено
    assert len(rows) > 0
    assert len(blocks) > 0
    assert len(inputs) > 0
