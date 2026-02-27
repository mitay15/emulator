import json
import sys
from pathlib import Path

LAST = Path("reports/last_run/metrics.json")
PREV = Path("reports/previous_run/metrics.json")


def load(path):
    if not path.exists():
        return None
    return json.loads(path.read_text())


def compare_metrics(prev, last):
    keys = ["eventualBG_mae", "rate_mae", "autosens_mae", "iob_mae"]

    regressions = []
    for k in keys:
        if prev.get(k) is None or last.get(k) is None:
            continue
        if last[k] > prev[k]:
            regressions.append((k, prev[k], last[k]))

    return regressions


def main():
    prev = load(PREV)
    last = load(LAST)

    if prev is None:
        print("No previous metrics found — skipping regression check.")
        return 0

    regressions = compare_metrics(prev, last)

    if regressions:
        print("Regression detected:")
        for key, prev, last in regressions:
            print(f"  {key}: was {prev}, now {last}")
        return 1

    print("No regression — algorithm improved or stayed equal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
