# tools/show_inputs.py
import json
from pathlib import Path

idx = int(input("Введите номер блока: "))

path = Path("data/cache") / f"inputs_before_algo_block_{idx}.json"

data = json.loads(path.read_text("utf-8"))
inputs = data["inputs"]

out = {
    "glucose_status": inputs["glucose_status"],
    "profile": inputs["profile"],
    "autosens": inputs["autosens"],
    "meal": inputs["meal"],
    "iob_data_array_first3": inputs["iob_data_array"][:3],
}

print(json.dumps(out, indent=2, ensure_ascii=False))
