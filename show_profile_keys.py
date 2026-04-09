import json
from pathlib import Path

p = Path("data/cache/inputs_before_algo_block_00001.json")  # поменяй при необходимости
if not p.exists():
    print("FILE_NOT_FOUND", p)
else:
    d = json.load(open(p, "r", encoding="utf-8"))
    prof = d.get("inputs", {}).get("profile")
    if not prof:
        print("PROFILE_NOT_FOUND")
    else:
        keys = list(prof.keys())
        print("PROFILE_KEYS_COUNT:", len(keys))
        print(keys[:200])  # покажем первые 200 ключей
