import json
from pathlib import Path

import numpy as np
import pandas as pd

DIFFS_PATH = Path("tests/diffs_with_inputs.csv")
METRICS_PATH = Path("reports/last_run/metrics.json")


def mae(a, b):
    return float(np.abs(a - b).mean())


def rmse(a, b):
    return float(np.sqrt(((a - b) ** 2).mean()))


def match_pct(a, b, tol=0.05):
    return float((np.abs(a - b) <= tol).mean())


def compute_metrics():
    df = pd.read_csv(DIFFS_PATH)

    metrics = {
        "eventualBG_mae": mae(df["aaps_eventual_ref"], df["py_eventual"]),
        "eventualBG_rmse": rmse(df["aaps_eventual_ref"], df["py_eventual"]),
        "eventualBG_max": float(np.abs(df["aaps_eventual_ref"] - df["py_eventual"]).max()),
        "rate_mae": mae(df["aaps_rate_ref"], df["py_rate"]),
        "rate_match_pct": match_pct(df["aaps_rate_ref"], df["py_rate"], tol=0.05),
        # autosens_ref отсутствует в RT → None
        "autosens_mae": None,
        # IOB сравниваем правильно
        "iob_mae": mae(df["iob_ref"], df["iob_py"]) if "iob_ref" in df and "iob_py" in df else None,
        # insulinReq сравниваем правильно
        "insulinReq_mae": mae(df["aaps_insreq_ref"], df["py_insreq"]) if "aaps_insreq_ref" in df else None,
        # SMB отсутствует в RT → None
        "smb_mae": None,
        # temp basal отсутствует в RT → None
        "temp_basal_match_pct": None,
        "quality_score": None,  # пересчитаем позже
        "count": int(len(df)),
    }

    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("Metrics saved to", METRICS_PATH)
    return metrics


if __name__ == "__main__":
    compute_metrics()
