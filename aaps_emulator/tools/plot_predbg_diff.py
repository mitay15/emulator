# tools/plot_predbg_diff.py
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt


def _load_mismatch_file(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _ensure_out_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def plot_predbg_diff(
    aaps_pred: List[float],
    py_pred: List[float],
    diffs: Optional[List[Optional[float]]],
    out_path: Path,
    title: str = "",
    show_diff: bool = True,
) -> None:
    """
    Универсальная функция:
    - рисует AAPS vs Python
    - если diffs не None и show_diff=True — добавляет нижний график ΔBG
    """
    _ensure_out_dir(out_path)

    if show_diff and diffs is not None:
        fig, (ax1, ax2) = plt.subplots(
            2,
            1,
            figsize=(10, 8),
            sharex=True,
            gridspec_kw={"height_ratios": [3, 1]},
        )

        ax1.plot(range(len(aaps_pred)), aaps_pred, label="AAPS (Kotlin)", color="blue", linewidth=1.5)
        ax1.plot(range(len(py_pred)), py_pred, label="Python emulator", color="orange", linewidth=1.5)
        ax1.set_ylabel("BG")
        ax1.set_title(title or "Predicted BG: AAPS vs Python")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        clean_x = [i for i, d in enumerate(diffs) if d is not None]
        clean_d = [d for d in diffs if d is not None]

        ax2.axhline(0, color="black", linewidth=1)
        if clean_x:
            ax2.plot(clean_x, clean_d, label="Python - AAPS", color="red", linewidth=1)
        ax2.set_xlabel("Index")
        ax2.set_ylabel("Δ BG")
        ax2.grid(True, alpha=0.3)

        fig.tight_layout()
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
    else:
        plt.figure(figsize=(10, 5))
        plt.plot(range(len(aaps_pred)), aaps_pred, label="AAPS (Kotlin)")
        plt.plot(range(len(py_pred)), py_pred, label="Python emulator")
        plt.title(title or "Predicted BG: AAPS vs Python")
        plt.xlabel("Index")
        plt.ylabel("BG")
        plt.legend()
        plt.tight_layout()
        plt.savefig(out_path)
        plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot predicted BG diff (AAPS vs Python) from mismatch JSON."
    )
    parser.add_argument(
        "--mismatch",
        type=str,
        required=True,
        help="Path to mismatch_block_*.json file",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output PNG path (default: data/reports/predbg_diff/<name>.png)",
    )
    args = parser.parse_args()

    mismatch_path = Path(args.mismatch)
    data = _load_mismatch_file(mismatch_path)

    aaps_pred = data.get("predBGs_aaps") or []
    py_pred = data.get("predBGs_py") or []
    diffs = data.get("predBGs_diff") or data.get("predBGs_diffs") or None

    if not aaps_pred or not py_pred:
        raise SystemExit("No predBGs data in mismatch file.")

    if args.out:
        out_path = Path(args.out)
    else:
        out_dir = Path("data") / "reports" / "predbg_diff"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{mismatch_path.stem}.png"

    title = f"Predicted BG diff — {mismatch_path.name}"
    plot_predbg_diff(aaps_pred, py_pred, diffs, out_path, title=title, show_diff=True)
    print(f"Saved plot to: {out_path}")


if __name__ == "__main__":
    main()
