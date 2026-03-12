# aaps_emulator/visual/plot_predictions.py
from __future__ import annotations
import plotly.graph_objects as go


def plot_predictions(times, bgs, eventual):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=times,
        y=bgs,
        mode="lines+markers",
        name="BG"
    ))

    fig.add_trace(go.Scatter(
        x=times,
        y=eventual,
        mode="lines",
        name="eventualBG"
    ))

    fig.update_layout(
        title="AutoISF — BG vs eventualBG",
        xaxis_title="Время",
        yaxis_title="mg/dL",
        template="plotly_dark",
    )

    return fig
