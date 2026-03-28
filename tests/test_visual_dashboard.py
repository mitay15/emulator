# tests/test_visual_dashboard.py
from aaps_emulator.visual.dashboard import build_dashboard

def test_build_dashboard_rmse_present():
    sample = [
        {"datetime":"2026-01-01T00:00:00","eventual_bg":100,"aaps_eventual_bg":110},
        {"datetime":"2026-01-01T01:00:00","eventual_bg":120,"aaps_eventual_bg":115},
    ]
    fig = build_dashboard(sample, max_points=10)
    assert fig.layout.title.text is not None
    assert "RMSE eventualBG" in str(fig.layout.title.text)
    assert len(fig.data) >= 3
