import csv
from pathlib import Path

# make PLOTS_DIR relative to package root
BASE = Path(__file__).resolve().parent.parent
DIFFS_PATH = BASE / "tests" / "diffs_with_inputs.csv"
PLOTS_DIR = BASE / "tests" / "plots"


def load_diffs():
    rows = []
    with DIFFS_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:

            def fget(name):
                v = r.get(name)
                if v is None or v == "":
                    return None
                try:
                    return float(v)
                except Exception:
                    return None

            rows.append(
                {
                    "idx": int(r["idx"]),
                    "ts": float(r["ts_s"]),
                    "aaps_rate": fget("aaps_rate_ref"),
                    "py_rate": fget("py_rate"),
                    "aaps_eventual": fget("aaps_eventual_ref"),
                    "py_eventual": fget("py_eventual"),
                    "diff_eventual": fget("err_ev"),
                }
            )
    return rows


def plot_rate(rows, out_path: Path | None = None):
    import matplotlib.pyplot as plt

    plt.figure(figsize=(12, 5))
    plt.plot([r["ts"] for r in rows], [r["aaps_rate"] for r in rows], label="AAPS rate")
    plt.plot([r["ts"] for r in rows], [r["py_rate"] for r in rows], label="Python rate", linestyle="--")
    plt.legend()
    plt.title("AAPS vs Python — Rate")
    plt.xlabel("timestamp")
    plt.ylabel("U/h")
    plt.grid(True)
    plt.tight_layout()

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    target = out_path or (PLOTS_DIR / "rate_compare.png")
    plt.savefig(target)
    plt.close()


def plot_eventual(rows, out_path: Path | None = None):
    import matplotlib.pyplot as plt

    plt.figure(figsize=(12, 5))
    plt.plot([r["ts"] for r in rows], [r["aaps_eventual"] for r in rows], label="AAPS eventualBG")
    plt.plot([r["ts"] for r in rows], [r["py_eventual"] for r in rows], label="Python eventualBG", linestyle="--")
    plt.legend()
    plt.title("AAPS vs Python — eventualBG")
    plt.xlabel("timestamp")
    plt.ylabel("mmol/L")
    plt.grid(True)
    plt.tight_layout()

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    target = out_path or (PLOTS_DIR / "eventual_compare.png")
    plt.savefig(target)
    plt.close()


def plot_diffs(rows, out_path: Path | None = None):
    import matplotlib.pyplot as plt

    plt.figure(figsize=(12, 5))
    plt.plot([r["ts"] for r in rows], [r["diff_eventual"] for r in rows], label="diff eventualBG")
    plt.legend()
    plt.title("Diff eventualBG (Python - AAPS)")
    plt.xlabel("timestamp")
    plt.ylabel("mmol/L")
    plt.grid(True)
    plt.tight_layout()

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    target = out_path or (PLOTS_DIR / "diff_eventual.png")
    plt.savefig(target)
    plt.close()


def plot_scatter_rate(rows, out_path: Path | None = None):
    # Берём только строки, где оба значения существуют
    pairs = [(r["aaps_rate"], r["py_rate"]) for r in rows if r["aaps_rate"] is not None and r["py_rate"] is not None]

    if not pairs:
        print("No valid rate pairs for scatter plot")
        return

    aaps_rates = [p[0] for p in pairs]
    py_rates = [p[1] for p in pairs]

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(aaps_rates, py_rates, s=10)

    # диагональ
    m = max(max(aaps_rates), max(py_rates))
    ax.plot([0, m], [0, m], color="red")

    ax.set_title("Scatter: AAPS rate vs Python rate")
    ax.set_xlabel("AAPS rate")
    ax.set_ylabel("Python rate")
    ax.grid(True)
    plt.tight_layout()

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    target = out_path or (PLOTS_DIR / "scatter_rate.png")
    fig.savefig(target)
    plt.close(fig)


def main():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_diffs()

    plot_rate(rows)
    plot_eventual(rows)
    plot_diffs(rows)
    plot_scatter_rate(rows)

    print("Plots saved to:", PLOTS_DIR)


if __name__ == "__main__":
    main()
