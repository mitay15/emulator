from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def load_summary(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def generate_html(summary: Dict[str, Any], out_path: Path) -> None:
    rows: List[Dict[str, Any]] = summary.get("rows", [])
    mismatch_stats: Dict[str, Any] = summary.get("mismatch_stats", {})
    total_blocks = summary.get("total_blocks", 0)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    html = []
    html.append("<html><head><meta charset='utf-8'><title>AAPS parity report</title></head><body>")
    html.append("<h1>AAPS vs Python parity report</h1>")

    html.append(f"<p>Total blocks: {total_blocks}</p>")
    html.append("<h2>Mismatch stats</h2><ul>")
    for k, v in mismatch_stats.items():
        html.append(f"<li>{k}: {v}</li>")
    html.append("</ul>")

    html.append("<h2>PredBG metrics (first 20 blocks)</h2>")
    html.append("<table border='1' cellspacing='0' cellpadding='4'>")
    html.append("<tr><th>idx</th><th>MAE</th><th>RMSE</th><th>Max diff</th></tr>")
    for r in rows[:20]:
        html.append(
            f"<tr><td>{r.get('idx')}</td>"
            f"<td>{r.get('predBGs_mae', 0):.4f}</td>"
            f"<td>{r.get('predBGs_rmse', 0):.4f}</td>"
            f"<td>{r.get('predBGs_max_diff', 0):.4f}</td></tr>"
        )
    html.append("</table>")

    # Вставляем картинки, если есть
    heatmap_path = Path("reports/heatmaps/diff_heatmap.png")
    if heatmap_path.exists():
        html.append("<h2>Heatmap</h2>")
        html.append(f"<img src='../{heatmap_path.as_posix()}' alt='Heatmap' style='max-width:100%;'>")

    diff_dir = Path("reports/predbg_diff")
    if diff_dir.exists():
        html.append("<h2>Predicted BG diffs</h2>")
        for img in sorted(diff_dir.glob("*.png")):
            html.append(f"<div><p>{img.name}</p><img src='../{img.as_posix()}' style='max-width:100%;'></div>")

    html.append("</body></html>")

    out_path.write_text("\n".join(html), encoding="utf-8")


def main() -> None:
    summary_path = Path("reports/compare/summary.json")
    out_path = Path("reports/html/parity_report.html")

    if not summary_path.exists():
        raise SystemExit(f"No summary.json at {summary_path}")

    summary = load_summary(summary_path)
    generate_html(summary, out_path)
    print(f"HTML report saved to: {out_path}")


if __name__ == "__main__":
    main()
