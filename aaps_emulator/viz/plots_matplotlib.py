# aaps_emulator/viz/plots_matplotlib.py
from datetime import datetime
from pathlib import Path

import numpy as np


def plot_error_heatmap(rows, bin_by="hour", out_path: str | Path | None = None):
    """
    rows: list of dict with keys ts_s, aaps_eventual, py_eventual
    bin_by: "hour" or "day"
    out_path: optional path to save PNG; if None, returns matplotlib Figure
    """
    if not rows:
        print("No rows")
        return None

    # compute absolute error
    ts = np.array([r["ts_s"] for r in rows])
    err = np.array([abs((r.get("aaps_eventual") or 0) - (r.get("py_eventual") or 0)) for r in rows])

    # convert timestamps to datetime
    dt = [datetime.fromtimestamp(int(t)) for t in ts]

    if bin_by == "hour":
        keys = [d.replace(minute=0, second=0, microsecond=0) for d in dt]
    else:
        keys = [d.replace(hour=0, minute=0, second=0, microsecond=0) for d in dt]

    # aggregate
    uniq = sorted(set(keys))
    agg = []
    for u in uniq:
        vals = [e for k, e in zip(keys, err, strict=True) if k == u]
        agg.append(float(np.mean(vals)) if vals else 0.0)

    # import matplotlib only when plotting
    import matplotlib.pyplot as plt

    # plot heatmap-like bar
    fig, ax = plt.subplots(figsize=(12, 3))
    cmap = plt.get_cmap("hot")
    vmin = min(agg) if agg else 0.0
    vmax = max(agg) if agg and max(agg) > 0 else 1.0
    norm = plt.Normalize(vmin=vmin, vmax=vmax)
    colors = [cmap(norm(v)) for v in agg]
    ax.bar(range(len(uniq)), [1] * len(uniq), color=colors)
    ax.set_xticks(range(len(uniq)))
    ax.set_xticklabels(
        [u.strftime("%Y-%m-%d %H:%M") if bin_by == "hour" else u.strftime("%Y-%m-%d") for u in uniq],
        rotation=45,
        ha="right",
    )
    ax.set_yticks([])
    ax.set_title("Heatmap of |AAPS - PY| (aggregated)")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    fig.colorbar(sm, orientation="vertical", label="mean |Δ| mmol/L")
    plt.tight_layout()

    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        return out_path

    return fig

