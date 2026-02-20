# aaps_emulator/viz/plots_matplotlib.py
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

def plot_error_heatmap(rows, bin_by="hour"):
    """
    rows: list of dict with keys ts_s, aaps_eventual, py_eventual
    bin_by: "hour" or "day"
    """
    if not rows:
        print("No rows")
        return

    # compute absolute error
    ts = np.array([r["ts_s"] for r in rows])
    err = np.array([abs((r["aaps_eventual"] or 0) - (r["py_eventual"] or 0)) for r in rows])

    # convert timestamps to datetime
    dt = [datetime.fromtimestamp(int(t)) for t in ts]

    if bin_by == "hour":
        keys = [d.replace(minute=0, second=0, microsecond=0) for d in dt]
    else:
        keys = [d.replace(hour=0, minute=0, second=0, microsecond=0) for d in dt]

    # aggregate
    uniq = sorted(list({k for k in keys}))
    agg = []
    for u in uniq:
        vals = [e for k, e in zip(keys, err) if k == u]
        agg.append(np.mean(vals) if vals else 0.0)

    # plot heatmap-like bar
    fig, ax = plt.subplots(figsize=(12, 3))
    cmap = plt.get_cmap("hot")
    norm = plt.Normalize(vmin=min(agg), vmax=max(agg) if max(agg) > 0 else 1)
    colors = [cmap(norm(v)) for v in agg]
    ax.bar(range(len(uniq)), [1]*len(uniq), color=colors)
    ax.set_xticks(range(len(uniq)))
    ax.set_xticklabels([u.strftime("%Y-%m-%d %H:%M") if bin_by=="hour" else u.strftime("%Y-%m-%d") for u in uniq], rotation=45, ha="right")
    ax.set_yticks([])
    ax.set_title("Heatmap of |AAPS - PY| (aggregated)")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    fig.colorbar(sm, orientation="vertical", label="mean |Δ| mmol/L")
    plt.tight_layout()
    plt.show()
