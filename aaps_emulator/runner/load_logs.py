# aaps_emulator/runner/load_logs.py
from __future__ import annotations

import json
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


def _extract_objects_from_text(text: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if not text:
        return results

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # --- FIX: remove prefixes before Kotlin object ---
        for name in OBJECT_NAMES:
            marker = name + "("
            if marker in line:
                idx = line.index(marker)
                line = line[idx:]
                break
        # ---------------------------------------------------

        if not any(name + "(" in line for name in OBJECT_NAMES):
            continue

        for name in OBJECT_NAMES:
            marker = name + "("
            if marker in line:
                try:
                    idx = line.index(marker)
                    snippet = line[idx:]
                    parsed = parse_kotlin_object(snippet)
                    results.append(parsed)
                except Exception:
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
        v = data.get(key)
        if isinstance(v, list):
            return v

    return [data]


def _load_zip_file(path: Path) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    with zipfile.ZipFile(path, "r") as z:
        for name in z.namelist():
            lname = name.lower()
            try:
                with z.open(name) as f:
                    if lname.endswith(".json"):
                        try:
                            data = json.load(f)
                            if isinstance(data, list):
                                blocks.extend(data)
                            else:
                                blocks.append(data)
                        except Exception:
                            continue
                    elif lname.endswith(".log"):
                        try:
                            text = f.read().decode("utf-8", errors="ignore")
                            blocks.extend(_extract_objects_from_text(text))
                        except Exception:
                            continue
            except Exception:
                continue
    return blocks


def _iter_all_files_recursively(root: Path) -> List[Path]:
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in (".json", ".log", ".zip")
    )


def load_logs(path: str | Path) -> List[Dict[str, Any]]:
    p = Path(path)

    if p.is_dir():
        all_blocks: List[Dict[str, Any]] = []
        files = _iter_all_files_recursively(p)
        if not files:
            raise ValueError(f"В директории {p} не найдено ни одного файла .json/.log/.zip")

        for file in files:
            suf = file.suffix.lower()
            if suf == ".json":
                all_blocks.extend(_load_json_file(file))
            elif suf == ".log":
                all_blocks.extend(_load_log_file(file))
            elif suf == ".zip":
                all_blocks.extend(_load_zip_file(file))

        return all_blocks

    suf = p.suffix.lower()

    # поддержка AndroidAPS ZIP логов
    if suf == ".zip":
        return _load_zip_file(p)

    # поддержка .log.json (AndroidAPS иногда так пишет)
    if suf == ".json" or p.name.lower().endswith(".log.json"):
        return _load_json_file(p)

    # обычные .log
    if suf == ".log":
        return _load_log_file(p)

    raise ValueError(f"Неизвестный формат файла: {p}")
