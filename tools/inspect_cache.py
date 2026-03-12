# file: tools/inspect_cache.py
from pathlib import Path
import json

p1 = Path("aaps_emulator/data/cache/parsed_block_on_error.json")
p2 = Path("data/cache/failed_inputs_for_pipeline.json")

print("parsed exists:", p1.exists(), p1)
if p1.exists():
    txt = p1.read_text(encoding="utf-8")
    print("\n--- parsed_block_on_error.json (first 2000 chars) ---\n")
    print(txt[:2000])

print("\nfailed inputs exists:", p2.exists(), p2)
if p2.exists():
    try:
        txt2 = p2.read_text(encoding="utf-8")
        print("\n--- failed_inputs_for_pipeline.json (first 2000 chars) ---\n")
        print(txt2[:2000])
    except Exception as e:
        print("Could not read failed_inputs_for_pipeline.json:", e)
