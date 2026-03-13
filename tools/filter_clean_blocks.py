from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from runner.compare_runner import extract_blocks_from_logs


def save_clean_blocks(blocks: List[List[Dict[str, Any]]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    for idx, block in enumerate(blocks, start=1):
        out_path = out_dir / f"block_{idx:04d}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(block, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(blocks)} clean blocks to {out_dir}")


def main() -> None:
    logs_dir = Path("data") / "logs"
    assert logs_dir.exists(), f"Logs directory not found: {logs_dir}"

    paths = (
        list(logs_dir.rglob("*.json"))
        + list(logs_dir.rglob("*.zip"))
        + list(logs_dir.rglob("*.log"))
    )
    assert paths, f"No log files found in {logs_dir}"

    print(f"Found {len(paths)} log files. Extracting clean blocks...")

    # ВАЖНО: мы извлекаем block_objs, а не rows
    blocks = extract_blocks_from_logs(paths)

    out_dir = Path("data") / "clean"
    save_clean_blocks(blocks, out_dir)


if __name__ == "__main__":
    main()
