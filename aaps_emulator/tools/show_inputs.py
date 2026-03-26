# aaps_emulator/tools/show_inputs.py
import json
from pathlib import Path
from typing import Any, Dict

CACHE_DIR = Path("data") / "cache"

def load_block(idx: int) -> Dict[str, Any]:
    """Загрузить JSON блока по индексу. Бросает FileNotFoundError при отсутствии файла."""
    path = CACHE_DIR / f"inputs_before_algo_block_{idx}.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def format_block(data: Dict[str, Any]) -> Dict[str, Any]:
    """Подготовить словарь для вывода (без печати)."""
    inputs = data.get("inputs", {})
    return {
        "glucose_status": inputs.get("glucose_status"),
        "profile": inputs.get("profile"),
        "autosens": inputs.get("autosens"),
        "meal": inputs.get("meal"),
        "iob_data_array_first3": inputs.get("iob_data_array", [])[:3],
    }

def show_block(idx: int) -> None:
    """Загрузить и напечатать блок; обработать ошибки дружелюбно."""
    try:
        data = load_block(idx)
    except FileNotFoundError:
        print(f"Файл для блока {idx} не найден в {CACHE_DIR}.")
        return
    out = format_block(data)
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    # интерактивный запуск — только здесь
    try:
        raw = input("Введите номер блока: ").strip()
        idx = int(raw) if raw else 1
    except Exception:
        idx = 1
    show_block(idx)
