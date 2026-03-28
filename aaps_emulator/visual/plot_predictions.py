from __future__ import annotations
from typing import Iterable, Optional, List
import warnings
import plotly.graph_objects as go
from .colors import get_palette
from .utils import to_datetime, decimate_series

def plot_predictions(
    times: Iterable,
    bgs: Iterable,
    eventual: Iterable,
    palette: str = "default",
    max_points: int = 2000,
    export_path: Optional[str] = None,
    export_formats: Optional[List[str]] = None,
) -> go.Figure:
    pal = get_palette(palette)
    times_parsed = [to_datetime(t) for t in times]
    times_d, bgs_d = decimate_series(times_parsed, list(bgs), max_points=max_points)
    _, eventual_d = decimate_series(times_parsed, list(eventual), max_points=max_points)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times_d, y=bgs_d, mode="lines+markers", name="BG", line=dict(color=pal["bg"])))
    fig.add_trace(go.Scatter(x=times_d, y=eventual_d, mode="lines", name="eventualBG", line=dict(color=pal["eventual_py"], dash="dash")))

    fig.update_layout(title="AutoISF — BG vs eventualBG", xaxis_title="Time", yaxis_title="mg/dL", template="plotly_dark", height=480)
    fig.update_xaxes(rangeslider_visible=True)

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
