from __future__ import annotations

from typing import List, Dict, Optional
import warnings
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .colors import get_palette
from .utils import to_datetime, rmse, decimate_series


def build_dashboard(
    results: List[Dict],
    palette: str = "default",
    max_points: int = 2000,
    export_path: Optional[str] = None,
    export_formats: Optional[List[str]] = None,
) -> go.Figure:
    """
    Build dashboard with RMSE metrics, optional export, color theme and decimation.

    Parameters
    - results: list of dicts with keys described earlier
    - palette: palette name from colors.get_palette
    - max_points: maximum points per series before decimation
    - export_path: base path to save image(s) without extension, e.g. "out/dashboard"
    - export_formats: list like ["png","svg"] to export images (requires kaleido)
    """
    pal = get_palette(palette)

    times = [to_datetime(r.get("datetime")) for r in results]
    bg = [r.get("bg") for r in results]
    eventual_py = [r.get("eventual_bg") for r in results]
    eventual_aaps = [r.get("aaps_eventual_bg") for r in results]

    insulin_req_py = [r.get("insulin_req") for r in results]
    insulin_req_aaps = [r.get("aaps_insulin_req") for r in results]

    rate_py = [r.get("rate") for r in results]
    rate_aaps = [r.get("aaps_rate") for r in results]

    smb_py = [r.get("smb") for r in results]
    smb_aaps = [r.get("aaps_smb") for r in results]

    # compute RMSE for eventual BG where both exist
    rmse_val = rmse(eventual_py, eventual_aaps)
    rmse_text = f"RMSE eventualBG: {rmse_val:.2f} mg/dL" if rmse_val is not None else "RMSE eventualBG: N/A"

    # decimate series if large
    times_d, bg_d = decimate_series(times, bg, max_points=max_points)
    _, eventual_py_d = decimate_series(times, eventual_py, max_points=max_points)
    _, eventual_aaps_d = decimate_series(times, eventual_aaps, max_points=max_points)
    _, insulin_req_py_d = decimate_series(times, insulin_req_py, max_points=max_points)
    _, insulin_req_aaps_d = decimate_series(times, insulin_req_aaps, max_points=max_points)
    _, rate_py_d = decimate_series(times, rate_py, max_points=max_points)
    _, rate_aaps_d = decimate_series(times, rate_aaps, max_points=max_points)
    _, smb_py_d = decimate_series(times, smb_py, max_points=max_points)
    _, smb_aaps_d = decimate_series(times, smb_aaps, max_points=max_points)

    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.3, 0.2, 0.25, 0.25],
        subplot_titles=(
            "BG / eventualBG",
            "InsulinReq (Python vs AAPS)",
            "Basal rate (Python vs AAPS)",
            "SMB (Python vs AAPS)",
        ),
    )

    # Row 1
    fig.add_trace(
        go.Scatter(x=times_d, y=bg_d, name="BG", mode="lines+markers", marker=dict(size=6), line=dict(color=pal["bg"])),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=times_d, y=eventual_py_d, name="eventualBG (Python)", mode="lines", line=dict(color=pal["eventual_py"])),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=times_d, y=eventual_aaps_d, name="eventualBG (AAPS)", mode="lines", line=dict(dash="dot", color=pal["eventual_aaps"])),
        row=1, col=1
    )

    # Row 2
    fig.add_trace(go.Scatter(x=times_d, y=insulin_req_py_d, name="insulinReq (Python)", mode="lines+markers", line=dict(color=pal["insulin_py"])), row=2, col=1)
    fig.add_trace(go.Scatter(x=times_d, y=insulin_req_aaps_d, name="insulinReq (AAPS)", mode="lines+markers", line=dict(dash="dot", color=pal["insulin_aaps"])), row=2, col=1)

    # Row 3
    fig.add_trace(go.Scatter(x=times_d, y=rate_py_d, name="rate (Python)", mode="lines+markers", line=dict(color=pal["rate_py"])), row=3, col=1)
    fig.add_trace(go.Scatter(x=times_d, y=rate_aaps_d, name="rate (AAPS)", mode="lines+markers", line=dict(dash="dot", color=pal["rate_aaps"])), row=3, col=1)

    # Row 4 SMB
    fig.add_trace(go.Bar(x=times_d, y=smb_py_d, name="SMB (Python)", marker=dict(color=pal["smb_py"]), offsetgroup=0), row=4, col=1)
    fig.add_trace(go.Bar(x=times_d, y=smb_aaps_d, name="SMB (AAPS)", marker=dict(color=pal["smb_aaps"], opacity=0.6), offsetgroup=1), row=4, col=1)

    fig.update_layout(
        title=f"AutoISF dashboard — Python vs AAPS — {rmse_text}",
        template="plotly_dark",
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=1000,
        margin=dict(t=100),
    )

    fig.update_xaxes(rangeslider_visible=True)

    # optional export (robust fallback: warn and continue if export fails)
    if export_path and export_formats:
        for fmt in export_formats:
            out = f"{export_path}.{fmt}"
            try:
                fig.write_image(out)
            except Exception as e:
                warnings.warn(
                    f"Export failed for {out}: {e}. Skipping static export. To enable exports, ensure 'kaleido' is installed and a compatible Chromium/Chrome is available."
                )

    return fig
