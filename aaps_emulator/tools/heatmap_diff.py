# tools/heatmap_diff.py
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np

# --- ВАЖНО: правильный корень пакета ---
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def _load_summary(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _ensure_out_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def build_heatmap_matrix(rows: List[Dict[str, Any]], fields: List[str]) -> np.ndarray:
    """
    Строит матрицу |diff| для указанных полей.
    Строки — поля, столбцы — блоки.
    """
    matrix = []
    for field in fields:
        row_vals = []
        for r in rows:
            aaps_val = r.get(f"{field}_aaps")
            py_val = r.get(f"{field}_py")
            if aaps_val is None or py_val is None:
                row_vals.append(0.0)
            else:
                try:
                    row_vals.append(abs(float(py_val) - float(aaps_val)))
                except Exception:
                    row_vals.append(0.0)
        matrix.append(row_vals)
    return np.array(matrix)


def plot_heatmap(
    matrix: np.ndarray,
    fields: List[str],
    out_path: Path,
    title: str = "AAPS vs Python diff heatmap",
) -> None:
    _ensure_out_dir(out_path)

    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(matrix, aspect="auto", cmap="viridis")

    ax.set_yticks(range(len(fields)))
    ax.set_yticklabels(fields)

    ax.set_xlabel("Block index")
    ax.set_title(title)

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("|diff|")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build heatmap of AAPS vs Python diffs from summary.json"
    )
    parser.add_argument(
        "--summary",
        type=str,
        default=str(DATA / "reports" / "compare" / "summary.json"),
        help="Path to summary.json (from compare_runner)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(DATA / "reports" / "heatmaps" / "diff_heatmap.png"),
        help="Output PNG path",
    )
    args = parser.parse_args()

    summary_path = Path(args.summary)
    data = _load_summary(summary_path)
    rows = data.get("results") or []

    if not rows:
        raise SystemExit("No rows in summary.json")

    fields = [
        "eventualBG",
        "minPredBG",
        "minGuardBG",
        "insulinReq",
        "rate",
        "duration",
        "smb",
    ]

    matrix = build_heatmap_matrix(rows, fields)
    out_path = Path(args.out)
    plot_heatmap(matrix, fields, out_path)
    print(f"Saved heatmap to: {out_path}")


if __name__ == "__main__":
    main()
