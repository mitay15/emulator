# aaps_emulator/runner/load_logs.py
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from aaps_emulator.runner.kotlin_parser import parse_kotlin_object

OBJECT_NAMES = [
    "GlucoseStatusAutoIsf",
    "CurrentTemp",
    "IobTotal",
    "OapsProfileAutoIsf",
    "AutosensResult",
    "MealData",
    "RT",
    "Predictions",
]

OBJ_RE = re.compile(
    r".*?(?P<name>" + r"|".join(re.escape(n) for n in OBJECT_NAMES) + r")\s*\(",
    re.DOTALL,
)


def _extract_objects_from_text(text: str) -> List[Dict]:
    results = []

    # --- Ускорение: фильтруем строки, чтобы не парсить весь лог ---
    important = []
    for line in text.splitlines():
        if any(name + "(" in line for name in OBJECT_NAMES):
            important.append(line.strip())

    if not important:
        return []

    for line in important:
        for name in OBJECT_NAMES:
            marker = name + "("
            if marker in line:
                try:
                    idx = line.index(marker)
                    snippet = line[idx:]
                    parsed = parse_kotlin_object(snippet)
                    results.append(parsed)
                except Exception:
                    # игнорируем нераспарсенные строки
                    continue

    return results


def _load_log_file(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return _extract_objects_from_text(text)


def _load_json_file(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    for key in ("logs", "entries", "data"):
        if key in data and isinstance(data[key], list):
            return data[key]
    return [data]


def _load_zip_file(path: Path) -> List[Dict[str, Any]]:
    blocks = []
    with zipfile.ZipFile(path, "r") as z:
        for name in z.namelist():
            if name.lower().endswith(".json"):
                with z.open(name) as f:
                    try:
                        data = json.load(f)
                        if isinstance(data, list):
                            blocks.extend(data)
                        else:
                            blocks.append(data)
                    except Exception:
                        continue
            elif name.lower().endswith(".log"):
                with z.open(name) as f:
                    try:
                        text = f.read().decode("utf-8", errors="ignore")
                        blocks.extend(_extract_objects_from_text(text))
                    except Exception:
                        continue
    return blocks


def _iter_all_files_recursively(root: Path) -> List[Path]:
    """Рекурсивно собирает все файлы JSON/LOG/ZIP."""
    files = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".json", ".log", ".zip"):
            files.append(p)
    return sorted(files)


def load_logs(path: str | Path) -> List[Dict[str, Any]]:
    p = Path(path)

    # 1) Если путь — директория → рекурсивно ищем все JSON/LOG/ZIP
    if p.is_dir():
        all_blocks: List[Dict[str, Any]] = []
        files = _iter_all_files_recursively(p)

        if not files:
            raise ValueError(
                f"В директории {p} не найдено ни одного файла .json/.log/.zip"
            )

        for file in files:
            if file.suffix.lower() == ".json":
                all_blocks.extend(_load_json_file(file))
            elif file.suffix.lower() == ".log":
                all_blocks.extend(_load_log_file(file))
            elif file.suffix.lower() == ".zip":
                all_blocks.extend(_load_zip_file(file))

        return all_blocks

    # 2) Если путь — одиночный файл
    if p.suffix.lower() == ".zip":
        return _load_zip_file(p)
    if p.suffix.lower() == ".json":
        return _load_json_file(p)
    if p.suffix.lower() == ".log":
        return _load_log_file(p)

    raise ValueError(f"Неизвестный формат файла: {p}")
