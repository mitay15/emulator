import csv
import math
import subprocess
import sys
from pathlib import Path

WORST_PATH = Path("aaps_emulator/tests/autoisf_worst.csv")
DIFFS_PATH = Path("aaps_emulator/tests/diffs_with_inputs.csv")
REPORT_PATH = Path("aaps_emulator/tests/autoisf_report.txt")
WORST_CSV_PATH = Path("aaps_emulator/tests/autoisf_worst.csv")


def rmse(values: list[float]) -> float:
    if not values:
        return float("nan")
    return math.sqrt(sum(v * v for v in values) / len(values))


def load_diffs(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # безопасно приводим к float, если поле есть
            def fget(name: str, row=row) -> float:
                v = row.get(name)
                if v is None or v == "":
                    return 0.0
                try:
                    return float(v)
                except Exception:
                    return 0.0

            row["_idx"] = int(row.get("idx", "0"))
            row["_diff_eventual"] = fget("diff_eventual")
            row["_diff_insreq"] = fget("diff_insreq")
            row["_diff_rate"] = fget("diff_rate")
            row["_diff_duration"] = fget("diff_duration")
            rows.append(row)
    return rows


def compute_metrics(rows: list[dict]) -> dict:
    ev = [r["_diff_eventual"] for r in rows]
    ins = [r["_diff_insreq"] for r in rows]
    rate = [r["_diff_rate"] for r in rows]
    dur = [r["_diff_duration"] for r in rows]

    return {
        "rmse_eventual": rmse(ev),
        "rmse_insreq": rmse(ins),
        "rmse_rate": rmse(rate),
        "rmse_duration": rmse(dur),
        "max_eventual": max((abs(x) for x in ev), default=0.0),
        "max_insreq": max((abs(x) for x in ins), default=0.0),
        "max_rate": max((abs(x) for x in rate), default=0.0),
        "max_duration": max((abs(x) for x in dur), default=0.0),
    }


def select_worst(rows: list[dict]) -> list[dict]:
    # интегральная «сила ошибки» по всем полям
    def score(r: dict) -> float:
        return abs(r["_diff_eventual"]) + abs(r["_diff_insreq"]) + abs(r["_diff_rate"]) + abs(r["_diff_duration"])

    scored = [(score(r), r) for r in rows]
    scored.sort(key=lambda t: t[0], reverse=True)

    if not scored:
        return []

    # берём максимум из:
    # - топ-20
    # - все строки с score >= 50% от максимального
    max_score = scored[0][0]
    threshold = max_score * 0.5

    worst: list[dict] = []
    for i, (s, r) in enumerate(scored):
        if i < 20 or s >= threshold:
            worst.append(r)
        else:
            break
    return worst


def run_inspect_idx(idx: int) -> str:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "aaps_emulator.tools.inspect_idx", str(idx)],
            shell=False,
            capture_output=True,
            text=True,
            check=False,
        )
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        text = ""
        if out:
            text += out + "\n"
        if err:
            text += "\n[stderr]\n" + err + "\n"
        return text
    except Exception as e:
        return f"[inspect_idx {idx}] exception: {e}\n"


def write_worst_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    if not DIFFS_PATH.exists():
        print(f"Diffs file not found: {DIFFS_PATH}")
        print("Сначала запусти: python -m aaps_emulator.tools.dump_diffs_and_inputs")
        return

    rows = load_diffs(DIFFS_PATH)
    if not rows:
        print("No rows in diffs_with_inputs.csv")
        return

    metrics = compute_metrics(rows)
    worst_rows = select_worst(rows)

    write_worst_csv(worst_rows, WORST_CSV_PATH)

    lines: list[str] = []
    lines.append("=== AutoISF Python vs AAPS — FULL REPORT ===\n")
    lines.append(f"Total rows: {len(rows)}")
    lines.append(f"Worst rows saved to: {WORST_CSV_PATH}")
    lines.append("")

    lines.append("=== RMSE ===")
    lines.append(f"eventualBG: {metrics['rmse_eventual']:.6f}")
    lines.append(f"insulinReq: {metrics['rmse_insreq']:.6f}")
    lines.append(f"rate      : {metrics['rmse_rate']:.6f}")
    lines.append(f"duration  : {metrics['rmse_duration']:.6f}")
    lines.append("")

    lines.append("=== MAX ABS ERROR ===")
    lines.append(f"eventualBG: {metrics['max_eventual']:.6f}")
    lines.append(f"insulinReq: {metrics['max_insreq']:.6f}")
    lines.append(f"rate      : {metrics['max_rate']:.6f}")
    lines.append(f"duration  : {metrics['max_duration']:.6f}")
    lines.append("")

    lines.append("=== WORST CASE ROWS (auto-selected) ===")
    for r in worst_rows:
        idx = r["_idx"]
        score = abs(r["_diff_eventual"]) + abs(r["_diff_insreq"]) + abs(r["_diff_rate"]) + abs(r["_diff_duration"])
        lines.append(
            f"idx={idx:5d}  score={score:.6f}  "
            f"diff_eventual={r['_diff_eventual']:.6f}  "
            f"diff_insreq={r['_diff_insreq']:.6f}  "
            f"diff_rate={r['_diff_rate']:.6f}  "
            f"diff_duration={r['_diff_duration']:.6f}"
        )
    lines.append("")

    lines.append("=== DETAILED INSPECT FOR WORST CASES ===")
    for r in worst_rows:
        idx = r["_idx"]
        lines.append(f"\n--- inspect_idx {idx} ---")
        lines.append(run_inspect_idx(idx))

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"Report written to: {REPORT_PATH}")
    print(f"Worst rows CSV   : {WORST_CSV_PATH}")


def load_worst_rows():
    if not WORST_PATH.exists():
        return []
    with WORST_PATH.open() as f:
        return [int(x.strip()) for x in f if x.strip().isdigit()]


if __name__ == "__main__":
    main()
