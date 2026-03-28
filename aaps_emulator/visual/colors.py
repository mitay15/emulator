# aaps_emulator/visual/colors.py
from __future__ import annotations
from typing import Dict

PALETTES: Dict[str, Dict[str, str]] = {
    "default": {
        "bg": "#7f7f7f",
        "eventual_py": "#1f77b4",
        "eventual_aaps": "#ff7f0e",
        "insulin_py": "#9467bd",
        "insulin_aaps": "#8c564b",
        "rate_py": "#17becf",
        "rate_aaps": "#bcbd22",
        "smb_py": "#2ca02c",
        "smb_aaps": "#98df8a",
    },
    "high_contrast": {
        "bg": "#bdbdbd",
        "eventual_py": "#003f5c",
        "eventual_aaps": "#ff6e54",
        "insulin_py": "#7a5195",
        "insulin_aaps": "#ef5675",
        "rate_py": "#ffa600",
        "rate_aaps": "#2f4b7c",
        "smb_py": "#2ca02c",
        "smb_aaps": "#98df8a",
    },
}

def get_palette(name: str = "default"):
    return PALETTES.get(name, PALETTES["default"])
