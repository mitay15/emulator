# aaps_emulator/tools/autoisf_plotly_report.py
import csv
import logging
from pathlib import Path

DIFFS_PATH = Path("aaps_emulator/tests/diffs_with_inputs.csv")
WORST_PATH = Path("aaps_emulator/tests/autoisf_worst.csv")
HTML_OUT = Path("aaps_emulator/tests/autoisf_plotly_report.html")

logger = logging.getLogger(__name__)


def load_diffs(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:

            def fget(name):
                v = row.get(name)
                if v is None or v == "":
                    return None
                try:
                    return float(v)
                except Exception:
                    return None

            try:
                rows.append(
                    {
                        "idx": int(row["idx"]),
                        "ts": float(row["ts_s"]),
                        "aaps_rate": fget("aaps_rate_ref"),
                        "py_rate": fget("py_rate"),
                        "aaps_eventual": fget("aaps_eventual_ref"),
                        "py_eventual": fget("py_eventual"),
                        "diff_eventual": fget("err_ev"),
                        "bg": fget("bg"),
                        "delta": fget("delta"),
                        "autosens_ratio": fget("autosens_ratio"),
                        "profile_sens": fget("profile_sens"),
                        "profile_basal": fget("profile_basal"),
                    }
                )
            except Exception:
                logger.exception("load_diffs: skipping malformed row")
                continue
    return rows


def load_worst(path: Path):
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                rows.append(int(row["idx"]))
            except Exception:  # noqa: S112
                # malformed row, skip
                continue
    return rows


def _build_html_template(content: str) -> str:
    # Your HTML with qwebchannel and pybridge integration (keeps your JS)
    return f"""<html>
<head>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script>
    var pybridge = null;
    new QWebChannel(qt.webChannelTransport, function(channel) {{
        pybridge = channel.objects.pybridge;
    }});
    </script>
    <meta charset="utf-8" />
    <title>AutoISF Plotly Report</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
{content}
<script>
document.addEventListener("DOMContentLoaded", function() {{
    let plots = document.getElementsByClassName("plotly-graph-div");
    for (let p of plots) {{
        // attach click handler via Plotly events
        p.on('plotly_click', function(data) {{
            let txt = data.points[0].text;
            if (txt && pybridge) {{
                let idx = parseInt(txt.replace("idx=", ""));
                pybridge.selectIdx(idx);
            }}
        }});
    }}
}});
</script>
</body>
</html>"""


def main():
    # heavy imports inside main to avoid side effects on import
    try:
        import plotly.graph_objs as go
        from plotly.offline import plot as plot_offline
        from plotly.subplots import make_subplots
    except Exception as e:
        logger.exception("plotly import failed: %s", e)
        print("Plotly not available; cannot build plotly report.")
        return

    if not DIFFS_PATH.exists():
        print("No diffs file:", DIFFS_PATH)
        return

    diffs = load_diffs(DIFFS_PATH)
    if not diffs:
        print("No rows in diffs file:", DIFFS_PATH)
        return

    worst_idx = set(load_worst(WORST_PATH))

    # --- Scatter rate with worst-case labels ---
    pairs = [
        (d["aaps_rate"], d["py_rate"], d["idx"])
        for d in diffs
        if d["aaps_rate"] is not None and d["py_rate"] is not None
    ]
    aaps_rates = [p[0] for p in pairs]
    py_rates = [p[1] for p in pairs]
    idxs = [p[2] for p in pairs]

    scatter_all = go.Scatter(
        x=aaps_rates,
        y=py_rates,
        mode="markers",
        name="All points",
        marker=dict(size=6, color="rgba(0, 0, 150, 0.4)"),
        text=[f"idx={i}" for i in idxs],
        hovertemplate="AAPS: %{x}<br>Python: %{y}<br>%{text}",
    )

    worst_mask_x = []
    worst_mask_y = []
    worst_text = []
    for x, y, i in zip(aaps_rates, py_rates, idxs, strict=True):
        if i in worst_idx:
            worst_mask_x.append(x)
            worst_mask_y.append(y)
            worst_text.append(f"idx={i}")

    scatter_worst = go.Scatter(
        x=worst_mask_x,
        y=worst_mask_y,
        mode="markers+text",
        name="Worst cases",
        marker=dict(size=12, color="red", line=dict(width=2, color="black")),
        text=worst_text,
        textposition="top center",
        hovertemplate="AAPS: %{x}<br>Python: %{y}<br>%{text}",
    )

    max_val = max(aaps_rates + py_rates) if aaps_rates and py_rates else 1.0
    diag = go.Scatter(
        x=[0, max_val],
        y=[0, max_val],
        mode="lines",
        name="Ideal",
        line=dict(color="green", dash="dash"),
    )

    fig_scatter = go.Figure(data=[scatter_all, scatter_worst, diag])
    fig_scatter.update_layout(
        title="Scatter: AAPS rate vs Python rate (with worst-case labels)",
        xaxis_title="AAPS rate",
        yaxis_title="Python rate",
        height=600,
    )

    # --- Time series rate & eventual ---
    ts = [d["ts"] for d in diffs]
    a_rate = [d["aaps_rate"] for d in diffs]
    p_rate = [d["py_rate"] for d in diffs]
    a_ev = [d["aaps_eventual"] for d in diffs]
    p_ev = [d["py_eventual"] for d in diffs]
    diff_ev = [d["diff_eventual"] for d in diffs]

    fig_ts = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        subplot_titles=("Rate AAPS vs Python", "eventualBG AAPS vs Python"),
    )

    fig_ts.add_trace(go.Scatter(x=ts, y=a_rate, name="AAPS rate"), row=1, col=1)
    fig_ts.add_trace(
        go.Scatter(x=ts, y=p_rate, name="Python rate", line=dict(dash="dash")),
        row=1,
        col=1,
    )

    fig_ts.add_trace(go.Scatter(x=ts, y=a_ev, name="AAPS eventualBG"), row=2, col=1)
    fig_ts.add_trace(
        go.Scatter(x=ts, y=p_ev, name="Python eventualBG", line=dict(dash="dash")),
        row=2,
        col=1,
    )

    fig_ts.update_xaxes(title_text="timestamp", row=2, col=1)
    fig_ts.update_yaxes(title_text="U/h", row=1, col=1)
    fig_ts.update_yaxes(title_text="mmol/L", row=2, col=1)
    fig_ts.update_layout(height=700, title="Time series: rate & eventualBG")

    # --- 3D: BG × autosens × rate ---
    bg_vals_3d = [d["bg"] for d in diffs if d["bg"] is not None]
    ar_vals_3d = [d["autosens_ratio"] for d in diffs if d["autosens_ratio"] is not None]
    rate_vals_3d = [d["py_rate"] for d in diffs if d["py_rate"] is not None]

    fig_3d = go.Figure(
        data=[
            go.Scatter3d(
                x=bg_vals_3d,
                y=ar_vals_3d,
                z=rate_vals_3d,
                mode="markers",
                marker=dict(size=3, color=rate_vals_3d, colorscale="Viridis"),
            )
        ]
    )
    fig_3d.update_layout(
        title="3D: BG × autosens × rate",
        scene=dict(xaxis_title="BG", yaxis_title="autosens_ratio", zaxis_title="rate"),
        height=700,
    )

    # --- Heatmap sens × basal × diff_eventual ---
    sens_vals_hm = []
    basal_vals_hm = []
    diff_vals_hm = []

    for d in diffs:
        if d["profile_sens"] is not None and d["profile_basal"] is not None and d["diff_eventual"] is not None:
            sens_vals_hm.append(d["profile_sens"])
            basal_vals_hm.append(d["profile_basal"])
            diff_vals_hm.append(d["diff_eventual"])

    fig_sens_basal_hm = go.Figure(
        data=go.Histogram2d(
            x=sens_vals_hm,
            y=basal_vals_hm,
            z=diff_vals_hm,
            colorscale="RdBu",
            colorbar=dict(title="diff eventualBG"),
            nbinsx=20,
            nbinsy=20,
        )
    )
    fig_sens_basal_hm.update_layout(
        title="Heatmap: sens × basal × diff_eventual", xaxis_title="sens", yaxis_title="basal", height=600
    )

    # --- Heatmap diff_eventual vs AAPS eventual ---
    ev_pairs = [(a, d) for a, d in zip(a_ev, diff_ev, strict=True) if a is not None and d is not None]
    if ev_pairs:
        import numpy as np

        a_vals = np.array([p[0] for p in ev_pairs])
        d_vals = np.array([p[1] for p in ev_pairs])

        heat_fig = go.Figure(
            data=go.Histogram2d(
                x=a_vals,
                y=d_vals,
                colorscale="Viridis",
                nbinsx=20,
                nbinsy=20,
                colorbar=dict(title="count"),
            )
        )
        heat_fig.update_layout(
            title="Heatmap: AAPS eventualBG vs diff (Python - AAPS)",
            xaxis_title="AAPS eventualBG",
            yaxis_title="diff eventualBG",
        )
    else:
        heat_fig = go.Figure()
        heat_fig.update_layout(title="Heatmap: no data")

    # --- Rate vs BG ---
    bg_vals = [d["bg"] for d in diffs if d["bg"] is not None and d["py_rate"] is not None]
    rate_vals_bg = [d["py_rate"] for d in diffs if d["bg"] is not None and d["py_rate"] is not None]

    fig_bg_rate = go.Figure()
    fig_bg_rate.add_trace(
        go.Scatter(
            x=bg_vals,
            y=rate_vals_bg,
            mode="markers",
            name="rate vs BG",
            marker=dict(size=6, color="rgba(0, 150, 0, 0.5)"),
        )
    )
    fig_bg_rate.update_layout(
        title="Python rate vs BG",
        xaxis_title="BG",
        yaxis_title="rate (U/h)",
    )

    # --- Rate vs autosens_ratio ---
    ar_vals = [d["autosens_ratio"] for d in diffs if d["autosens_ratio"] is not None and d["py_rate"] is not None]
    rate_vals_ar = [d["py_rate"] for d in diffs if d["autosens_ratio"] is not None and d["py_rate"] is not None]

    fig_ar_rate = go.Figure()
    fig_ar_rate.add_trace(
        go.Scatter(
            x=ar_vals,
            y=rate_vals_ar,
            mode="markers",
            name="rate vs autosens_ratio",
            marker=dict(size=6, color="rgba(150, 0, 0, 0.5)"),
        )
    )
    fig_ar_rate.update_layout(
        title="Python rate vs autosens_ratio",
        xaxis_title="autosens_ratio",
        yaxis_title="rate (U/h)",
    )

    # --- Rate vs Profile Sens ---
    sens_vals = [d["profile_sens"] for d in diffs if d["profile_sens"] is not None]
    rate_vals_sens = [d["py_rate"] for d in diffs if d["profile_sens"] is not None]

    fig_sens = go.Figure()
    fig_sens.add_trace(
        go.Scatter(x=sens_vals, y=rate_vals_sens, mode="markers", marker=dict(size=6, color="rgba(0, 120, 200, 0.5)"))
    )
    fig_sens.update_layout(title="Rate vs Profile Sens", xaxis_title="sens", yaxis_title="rate")

    # --- Rate vs Profile Basal ---
    basal_vals = [d["profile_basal"] for d in diffs if d["profile_basal"] is not None]
    rate_vals_basal = [d["py_rate"] for d in diffs if d["profile_basal"] is not None]

    fig_basal = go.Figure()
    fig_basal.add_trace(
        go.Scatter(x=basal_vals, y=rate_vals_basal, mode="markers", marker=dict(size=6, color="rgba(200, 120, 0, 0.5)"))
    )
    fig_basal.update_layout(title="Rate vs Profile Basal", xaxis_title="basal", yaxis_title="rate")

    # --- Собираем всё в один HTML ---
    html_parts = []
    html_parts.append("<h1>AutoISF Plotly Report</h1>")

    html_parts.append("<h2>Scatter: rate</h2>")
    html_parts.append(plot_offline(fig_scatter, include_plotlyjs=False, output_type="div"))

    html_parts.append("<h2>Time series</h2>")
    html_parts.append(plot_offline(fig_ts, include_plotlyjs=False, output_type="div"))

    html_parts.append("<h2>Heatmap: eventualBG vs diff</h2>")
    html_parts.append(plot_offline(heat_fig, include_plotlyjs=False, output_type="div"))

    html_parts.append("<h2>Rate vs BG</h2>")
    html_parts.append(plot_offline(fig_bg_rate, include_plotlyjs=False, output_type="div"))

    html_parts.append("<h2>Rate vs autosens_ratio</h2>")
    html_parts.append(plot_offline(fig_ar_rate, include_plotlyjs=False, output_type="div"))

    html_parts.append("<h2>3D: BG × autosens × rate</h2>")
    html_parts.append(plot_offline(fig_3d, include_plotlyjs=False, output_type="div"))

    html_parts.append("<h2>Rate vs Profile Sens</h2>")
    html_parts.append(plot_offline(fig_sens, include_plotlyjs=False, output_type="div"))

    html_parts.append("<h2>Heatmap: sens × basal × diff_eventual</h2>")
    html_parts.append(plot_offline(fig_sens_basal_hm, include_plotlyjs=False, output_type="div"))

    html_parts.append("<h2>Rate vs Profile Basal</h2>")
    html_parts.append(plot_offline(fig_basal, include_plotlyjs=False, output_type="div"))

    content = "".join(html_parts)
    full_html = _build_html_template(content)

    HTML_OUT.write_text(full_html, encoding="utf-8")
    print("Plotly HTML report written to:", HTML_OUT)


if __name__ == "__main__":
    main()
