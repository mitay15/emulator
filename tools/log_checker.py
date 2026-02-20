import os
import math
import csv
from aaps_emulator.analysis.compare_runner import run_compare_on_all_logs

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def load_reference():
    path = os.path.join(ROOT, "tests", "reference_generated.csv")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def rmse(values):
    return math.sqrt(sum(v*v for v in values) / len(values)) if values else 0.0

def main():
    reference = load_reference()
    rows, blocks, inputs = run_compare_on_all_logs(os.path.join(ROOT, "logs"))

    print(f"Loaded {len(reference)} reference rows, {len(rows)} log rows")

    ev_err = []
    rate_err = []
    ins_err = []

    for ref, row in zip(reference, rows):
        def safe_float(x):
            if x is None:
                return 0.0
            if x == "":
                return 0.0
            try:
                return float(x)
            except:
                return 0.0

        rate_err.append(safe_float(row["aaps_rate"]) - safe_float(ref["aaps_rate"]))
        ev_err.append(safe_float(row["aaps_eventual"]) - safe_float(ref["aaps_eventual"]))
        ins_err.append(safe_float(row["aaps_insreq"]) - safe_float(ref["aaps_insreq"]))


    print("RMSE eventual:", rmse(ev_err))
    print("RMSE rate:", rmse(rate_err))
    print("RMSE insreq:", rmse(ins_err))

if __name__ == "__main__":
    main()
