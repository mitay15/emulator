import csv
import math
from pathlib import Path

from aaps_emulator.core.autoisf_algorithm import determine_basal_autoisf


# --- simple mocks for inputs ---
class GS:
    def __init__(self, bg, delta):
        self.glucose = bg
        self.delta = delta


class Profile:
    def __init__(self):
        self.variable_sens = 6.0
        self.sens = 6.0
        self.target_bg = 6.4
        self.max_basal = 3.0
        self.current_basal = 1.0
        self.max_delta_rate = 2.0
        self.enableSMB_always = False
        self.smb_delivery_ratio = 0.5


class Autosens:
    def __init__(self):
        self.ratio = 1.0


class Meal:
    pass


class TempBasal:
    def __init__(self):
        self.duration = 0


# --- helpers ---
def rmse(values):
    if not values:
        return float("nan")
    return math.sqrt(sum(v * v for v in values) / len(values))


def read_reference_csv(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "timestamp": row["timestamp"],
                    "bg": float(row["bg"]),
                    "delta": float(row["delta"]),
                    "eventualBG_aaps": float(row["eventualBG"]),
                    "insulinReq_aaps": float(row["insulinReq"]),
                    "rate_aaps": float(row["rate"]),
                    "duration_aaps": float(row["duration"]),
                }
            )
    return rows


def run_python_autoisf(rows):
    out = []
    profile = Profile()
    autosens = Autosens()
    meal = Meal()
    temp = TempBasal()

    for r in rows:
        gs = GS(r["bg"], r["delta"])

        res = determine_basal_autoisf(
            glucose_status=gs,
            currenttemp=temp,
            iob_data_array=[],
            profile=profile,
            autosens_data=autosens,
            meal_data=meal,
            rt=None,
            trace_mode=False,
        )

        out.append(
            {
                "eventualBG_py": res.eventualBG,
                "insulinReq_py": res.insulinReq,
                "rate_py": res.rate,
                "duration_py": res.duration,
            }
        )

    return out


def compare(aaps_rows, py_rows):
    diffs = []
    for i, (a, p) in enumerate(zip(aaps_rows, py_rows, strict=True)):
        diffs.append(
            {
                "i": i,
                "timestamp": a["timestamp"],
                "eventualBG_err": p["eventualBG_py"] - a["eventualBG_aaps"],
                "insulinReq_err": p["insulinReq_py"] - a["insulinReq_aaps"],
                "rate_err": p["rate_py"] - a["rate_aaps"],
                "duration_err": p["duration_py"] - a["duration_aaps"],
            }
        )
    return diffs


def print_summary(diffs):
    fields = ["eventualBG_err", "insulinReq_err", "rate_err", "duration_err"]

    print("\n=== RMSE ===")
    for f in fields:
        values = [d[f] for d in diffs]
        print(f"{f}: {rmse(values):.4f}")

    print("\n=== MAX ERRORS ===")
    for f in fields:
        values = [abs(d[f]) for d in diffs]
        print(f"{f}: {max(values):.4f}")


def print_top_errors(diffs, field, n=20):
    print(f"\n=== TOP {n} ERRORS for {field} ===")
    sorted_rows = sorted(diffs, key=lambda d: abs(d[field]), reverse=True)
    for d in sorted_rows[:n]:
        print(f"{d['i']:5d}  ts={d['timestamp']}  err={d[field]:.4f}")


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m aaps_emulator.tools.autoisf_diff reference.csv")
        return

    ref_path = Path(sys.argv[1])
    print(f"Loading reference: {ref_path}")

    aaps_rows = read_reference_csv(ref_path)
    py_rows = run_python_autoisf(aaps_rows)
    diffs = compare(aaps_rows, py_rows)

    print_summary(diffs)

    for field in ["eventualBG_err", "insulinReq_err", "rate_err", "duration_err"]:
        print_top_errors(diffs, field)


if __name__ == "__main__":
    main()
