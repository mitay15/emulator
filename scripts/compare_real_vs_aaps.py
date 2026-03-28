# scripts/compare_real_vs_aaps.py
from __future__ import annotations
import json
import glob
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import csv

from aaps_emulator.visual.dashboard import build_dashboard
from aaps_emulator.visual.plot_predictions import plot_predictions
from aaps_emulator.visual.utils import to_datetime, rmse as rmse_fn

OUT = Path("out")
OUT.mkdir(exist_ok=True)

CACHE_GLOB = "data/cache/inputs_before_algo_block_*.json"

def load_first_cache_file() -> List[Dict]:
    files = sorted(glob.glob(CACHE_GLOB))
    if not files:
        raise FileNotFoundError(f"No cache files found with pattern {CACHE_GLOB}")
    path = files[0]
    print("Using cache file:", path)
    data = json.load(open(path, encoding="utf-8"))
    # try common shapes
    if isinstance(data, list):
        raw = data
    elif isinstance(data, dict):
        if "results" in data and isinstance(data["results"], list):
            raw = data["results"]
        elif "inputs" in data:
            inp = data["inputs"]
            if isinstance(inp, list):
                raw = inp
            elif isinstance(inp, dict):
                # try common keys
                for k in ("glucose_status", "history", "points"):
                    if k in inp and isinstance(inp[k], list):
                        raw = inp[k]
                        break
                else:
                    raw = [inp]
        else:
            raw = [data]
    else:
        raw = []
    return raw

def normalize_point(p: Dict) -> Dict:
    # map common names to expected keys
    return {
        "datetime": p.get("datetime") or p.get("time") or p.get("timestamp"),
        "bg": p.get("bg") or p.get("glucose") or p.get("sgv"),
        "eventual_bg": p.get("eventual_bg") or p.get("eventualBG") or p.get("predicted_bg"),
        "aaps_eventual_bg": p.get("aaps_eventual_bg") or p.get("aaps_eventualBG"),
        "insulin_req": p.get("insulin_req") or p.get("insulinRequirement"),
        "aaps_insulin_req": p.get("aaps_insulin_req"),
        "rate": p.get("rate") or p.get("basal_rate"),
        "aaps_rate": p.get("aaps_rate"),
        "smb": p.get("smb") or p.get("small_bolus") or p.get("temp_bolus"),
        "aaps_smb": p.get("aaps_smb"),
    }

def build_aligned_pairs(results: List[Dict]) -> List[Tuple]:
    """
    Return list of tuples (dt, eventual_py, eventual_aaps, bg, insulin_py, insulin_aaps, rate_py, rate_aaps, smb_py, smb_aaps)
    dt is datetime or None if unparsable
    """
    rows = []
    for p in results:
        n = normalize_point(p)
        dt = to_datetime(n["datetime"])
        rows.append((
            dt,
            n["eventual_bg"],
            n["aaps_eventual_bg"],
            n["bg"],
            n["insulin_req"],
            n["aaps_insulin_req"],
            n["rate"],
            n["aaps_rate"],
            n["smb"],
            n["aaps_smb"],
        ))
    # sort by datetime (None go last)
    rows.sort(key=lambda r: (r[0] is None, r[0]))
    return rows

def compute_metrics(pairs: List[Tuple]) -> Dict[str, Optional[float]]:
    eventual_py = [a for (_, a, _, *rest) in pairs]
    eventual_aaps = [b for (_, _, b, *rest) in pairs]
    # RMSE and MAE using utils.rmse for RMSE; implement MAE and bias here
    rmse_val = rmse_fn(eventual_py, eventual_aaps)
    # MAE and bias
    s = 0.0
    sabs = 0.0
    n = 0
    for x, y in zip(eventual_py, eventual_aaps):
        if x is None or y is None:
            continue
        try:
            dx = float(x) - float(y)
        except Exception:
            continue
        s += dx
        sabs += abs(dx)
        n += 1
    mae = (sabs / n) if n else None
    bias = (s / n) if n else None
    coverage = sum(1 for v in eventual_aaps if v is not None) / len(eventual_aaps) if eventual_aaps else 0.0
    return {"rmse": rmse_val, "mae": mae, "bias": bias, "pairs": n, "coverage": coverage}

def save_pairs_csv(pairs: List[Tuple], out_csv: Path):
    headers = ["datetime","eventual_py","eventual_aaps","bg","insulin_py","insulin_aaps","rate_py","rate_aaps","smb_py","smb_aaps"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for row in pairs:
            # convert datetime to ISO if present
            dt = row[0].isoformat() if row[0] is not None else ""
            w.writerow([dt] + list(row[1:]))

def main():
    raw = load_first_cache_file()
    if not raw:
        print("No points found in cache file.")
        return
    pairs = build_aligned_pairs(raw)
    metrics = compute_metrics(pairs)
    print("Metrics:")
    for k,v in metrics.items():
        print(f"  {k}: {v}")
    out_csv = OUT / "comparison_pairs.csv"
    save_pairs_csv(pairs, out_csv)
    print("Saved pairs CSV to", out_csv)

    # Build dashboard using normalized dicts (reconstruct list of dicts expected by build_dashboard)
    results = []
    for row in pairs:
        dt, eventual_py, eventual_aaps, bg, insulin_py, insulin_aaps, rate_py, rate_aaps, smb_py, smb_aaps = row
        results.append({
            "datetime": dt.isoformat() if dt else None,
            "bg": bg,
            "eventual_bg": eventual_py,
            "aaps_eventual_bg": eventual_aaps,
            "insulin_req": insulin_py,
            "aaps_insulin_req": insulin_aaps,
            "rate": rate_py,
            "aaps_rate": rate_aaps,
            "smb": smb_py,
            "aaps_smb": smb_aaps,
        })

    # plot and export (export optional)
    fig = build_dashboard(results, palette="default", max_points=2000, export_path=str(OUT / "dashboard"), export_formats=["png"])
    print("Dashboard title:", fig.layout.title.text)
    fig.show()

    # predictions plot
    times = [r["datetime"] for r in results]
    bgs = [r["bg"] for r in results]
    eventual = [r["eventual_bg"] for r in results]
    fig2 = plot_predictions(times, bgs, eventual, palette="default", max_points=2000, export_path=str(OUT / "predictions"), export_formats=["png"])
    fig2.show()
    print("Done.")

if __name__ == "__main__":
    main()
