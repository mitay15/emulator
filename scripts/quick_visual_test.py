from aaps_emulator.visual.dashboard import build_dashboard
from aaps_emulator.visual.plot_predictions import plot_predictions

sample = [
    {"datetime": "2026-01-15T08:00:00", "bg": 120, "eventual_bg": 110, "aaps_eventual_bg": 112,
     "insulin_req": 0.5, "aaps_insulin_req": 0.6, "rate": 0.8, "aaps_rate": 0.75, "smb": 0.0, "aaps_smb": 0.0},
    {"datetime": "2026-01-15T09:00:00", "bg": 130, "eventual_bg": 115, "aaps_eventual_bg": 118,
     "insulin_req": 0.6, "aaps_insulin_req": 0.65, "rate": 0.9, "aaps_rate": 0.9, "smb": 0.2, "aaps_smb": 0.2},
    {"datetime": "2026-01-15T10:00:00", "bg": 125, "eventual_bg": 113, "aaps_eventual_bg": None,
     "insulin_req": 0.55, "aaps_insulin_req": None, "rate": 0.85, "aaps_rate": None, "smb": 0.0, "aaps_smb": 0.0},
]

fig = build_dashboard(sample, palette="default", max_points=500, export_path="out/dashboard", export_formats=["png","svg"])
print("Title:", fig.layout.title.text)
fig.show()

fig2 = plot_predictions([p["datetime"] for p in sample], [p["bg"] for p in sample], [p["eventual_bg"] for p in sample])
fig2.show()
