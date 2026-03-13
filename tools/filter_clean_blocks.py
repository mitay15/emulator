from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from runner.compare_runner import compare_logs


def save_clean_blocks(clean_rows: List[Dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    for r in clean_rows:
        idx = r.get("idx")
        out_path = out_dir / f"block_{idx:04d}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(clean_rows)} clean blocks to {out_dir}")


def main() -> None:
    logs_dir = Path("data") / "logs"
    assert logs_dir.exists(), f"Logs directory not found: {logs_dir}"

    # Собираем все файлы логов
    paths = (
        list(logs_dir.rglob("*.json"))
        + list(logs_dir.rglob("*.zip"))
        + list(logs_dir.rglob("*.log"))
    )
    assert paths, f"No log files found in {logs_dir}"

    print(f"Found {len(paths)} log files. Running compare...")

    stats = compare_logs(paths=paths, fast=False, return_stats=True)
    rows = stats.get("results") or []

    # Фильтруем только чистые блоки
    clean_rows = [r for r in rows if not r.get("fallback")]

    print(f"Total blocks: {len(rows)}")
    print(f"Clean blocks: {len(clean_rows)}")
    print(f"Fallback blocks: {len(rows) - len(clean_rows)}")

    out_dir = Path("tests") / "data" / "aaps_parity"
    save_clean_blocks(clean_rows, out_dir)


if __name__ == "__main__":
    main()
