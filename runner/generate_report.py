# aaps_emulator/runner/generate_report.py
from __future__ import annotations
from pathlib import Path
from typing import List, Dict

import pandas as pd


def save_csv(results: List[Dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results)
    df.to_csv(path, index=False)
    return path
