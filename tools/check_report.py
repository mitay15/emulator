# tools/check_report.py
import json
from pathlib import Path

report = json.loads((Path("data/report/report.json")).read_text(encoding="utf-8"))
mm = report["mismatches"]
assert sum(mm.values()) == 0, mm
print("OK: all mismatches == 0 on", report["total_blocks"], "blocks")
