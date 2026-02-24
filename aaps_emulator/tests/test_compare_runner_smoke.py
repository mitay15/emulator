from pathlib import Path
from aaps_emulator.compare.compare_runner import run_compare_on_log


def test_compare_runner_smoke(tmp_path):
    # путь к маленькому логу
    log_path = Path("aaps_emulator/tests/fixtures/small_rt.log")

    # куда писать результат
    out_csv = tmp_path / "diffs.csv"

    # запускаем сравнение
    run_compare_on_log(log_path, out_csv)

    # файл должен появиться
    assert out_csv.exists()

    # и быть непустым
    text = out_csv.read_text().strip()
    assert len(text) > 0
