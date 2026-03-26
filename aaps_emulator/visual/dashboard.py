# aaps_emulator/visual/dashboard.py
from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def build_dashboard(results: list[dict]) -> go.Figure:
    times = [r["datetime"] for r in results]
    bg = [r["bg"] for r in results]
    eventual_py = [r["eventual_bg"] for r in results]
    eventual_aaps = [r.get("aaps_eventual_bg") for r in results]

    insulin_req_py = [r["insulin_req"] for r in results]
    insulin_req_aaps = [r.get("aaps_insulin_req") for r in results]

    rate_py = [r["rate"] for r in results]
    rate_aaps = [r.get("aaps_rate") for r in results]

    smb_py = [r["smb"] for r in results]
    smb_aaps = [r.get("aaps_smb") for r in results]

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

    # Row 1: BG + eventualBG
    fig.add_trace(
        go.Scatter(x=times, y=bg, name="BG", mode="lines+markers"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=times, y=eventual_py, name="eventualBG (Python)", mode="lines"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=eventual_aaps,
            name="eventualBG (AAPS)",
            mode="lines",
            line=dict(dash="dot"),
        ),
        row=1,
        col=1,
    )

    # Row 2: insulinReq
    fig.add_trace(
        go.Scatter(
            x=times, y=insulin_req_py, name="insulinReq (Python)", mode="lines+markers"
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=insulin_req_aaps,
            name="insulinReq (AAPS)",
            mode="lines+markers",
            line=dict(dash="dot"),
        ),
        row=2,
        col=1,
    )

    # Row 3: basal rate
    fig.add_trace(
        go.Scatter(x=times, y=rate_py, name="rate (Python)", mode="lines+markers"),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=times,
            y=rate_aaps,
            name="rate (AAPS)",
            mode="lines+markers",
            line=dict(dash="dot"),
        ),
        row=3,
        col=1,
    )

    # Row 4: SMB
    fig.add_trace(
        go.Bar(x=times, y=smb_py, name="SMB (Python)"),
        row=4,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=times,
            y=smb_aaps,
            name="SMB (AAPS)",
            marker=dict(opacity=0.5),
        ),
        row=4,
        col=1,
    )

    fig.update_layout(
        title="AutoISF dashboard — Python vs AAPS",
        template="plotly_dark",
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig
