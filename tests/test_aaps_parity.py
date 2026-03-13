import json
from pathlib import Path

from runner.compare_runner import compare_logs


def test_aaps_parity_clean_blocks():
    """
    Тест проверяет совпадение Python-алгоритма с AAPS 3.4
    только на чистых (не-fallback) блоках.
    """

    clean_dir = Path("tests/data/aaps_parity")
    assert clean_dir.exists(), f"Directory not found: {clean_dir}"

    # Собираем все clean-блоки
    clean_blocks = sorted(clean_dir.glob("block_*.json"))
    assert clean_blocks, "No clean blocks found. Run tools/filter_clean_blocks.py first."

    mismatches = []

    for block_file in clean_blocks:
        with block_file.open("r", encoding="utf-8") as f:
            row = json.load(f)

        # На всякий случай — пропускаем fallback
        if row.get("fallback"):
            continue

        # compare_logs ожидает список путей логов,
        # но мы уже имеем готовый row → вызываем внутреннюю функцию
        # поэтому используем compare_logs в режиме single-block
        stats = compare_logs(paths=[row["log_path"]], fast=False, return_stats=True)

        # clean-блоки используют глобальный idx — вставляем его вручную
        for r in stats["results"]:
            r["idx"] = row["idx"]


        # Находим соответствующий блок по индексу
        idx = row["idx"]
        result_row = next(r for r in stats["results"] if r["idx"] == idx)

        if result_row.get("fallback"):
            continue

        if result_row.get("mismatch"):
            mismatches.append((idx, result_row))

    assert not mismatches, f"Mismatches found in {len(mismatches)} blocks"
