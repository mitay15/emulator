# tools/generate_html_report_interactive.py
from __future__ import annotations
import json
from pathlib import Path

import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

SUMMARY_PATH = DATA / "reports" / "compare" / "summary.json"
CACHE_DIR = DATA / "cache"
OUT_HTML = DATA / "reports" / "html" / "parity_report_interactive.html"

# Поля для сравнения: (json_key_prefix, label)
FIELDS = [
    ("eventualBG", "eventualBG"),
    ("variable_sens", "variable_sens"),
    ("minPredBG", "minPredBG"),
    ("minGuardBG", "minGuardBG"),
    ("insulinReq", "insulinReq"),
    ("rate", "rate"),
    ("duration", "duration"),
    ("smb", "smb"),
]


def load_inputs_block(idx: int):
    """Load original AAPS block to get predBGs_aaps."""
    path = CACHE_DIR / f"inputs_before_algo_block_{idx}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_block_mismatch_fields(r: dict) -> list[str]:
    """Вернуть список полей, где есть расхождение AAPS vs Python."""
    mismatched = []
    for key, label in FIELDS:
        a = r.get(f"{key}_aaps")
        p = r.get(f"{key}_py")
        if a != p:
            mismatched.append(label)
    return mismatched


def build_heatmap(results):
    """Build interactive heatmap of mismatches."""
    matrix = []
    for r in results:
        row = []
        for key, _label in FIELDS:
            a = r.get(f"{key}_aaps")
            p = r.get(f"{key}_py")
            row.append(0 if a == p else 1)
        matrix.append(row)

    # Подсветка строк
    row_colors = [
        "rgba(255, 200, 200, 0.4)" if any(v == 1 for v in row)
        else "rgba(200, 255, 200, 0.2)"
        for row in matrix
    ]

    fig = px.imshow(
        matrix,
        labels=dict(x="Field", y="Block index", color="Mismatch"),
        x=[label for _key, label in FIELDS],
        y=[r["idx"] for r in results],
        color_continuous_scale=["#00cc00", "#ff0000"],  # зелёный → красный
        text_auto=True
    )

    # Добавляем подсветку строк
    for i, color in enumerate(row_colors):
        fig.add_shape(
            type="rect",
            x0=-0.5, x1=len(FIELDS) - 0.5,
            y0=i - 0.5, y1=i + 0.5,
            fillcolor=color,
            line_width=0,
            layer="below"
        )

    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def build_predbg_plot(r, aaps_block):
    """Build interactive AAPS vs Python predBGs plot."""
    py = r.get("predBGs_py") or []
    aaps = aaps_block.get("predBGs") if aaps_block else []

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=aaps, mode="lines+markers", name="AAPS (Kotlin)"))
    fig.add_trace(go.Scatter(y=py, mode="lines+markers", name="Python emulator"))

    fig.update_layout(
        title=f"Predicted BG — block {r['idx']}",
        xaxis_title="Step",
        yaxis_title="BG",
        template="plotly_white",
        height=400,
    )

    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def main():
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)

    with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
        summary = json.load(f)

    results = summary["results"]

    mismatch_blocks = [
        r for r in results
        if r.get("predBGs_max_diff", 0) > 0
    ]
    all_blocks = [
        r for r in results
        if r.get("predBGs_py")
    ]

    html = []
    html.append("<html><head>")
    html.append("<meta charset='utf-8'/>")
    html.append("<script src='https://cdn.plot.ly/plotly-latest.min.js'></script>")
    html.append("""
<style>
body { font-family: Arial, sans-serif; margin: 20px; }
.accordion { background: #eee; padding: 10px; cursor: pointer; margin-top: 10px; border-radius: 5px; }
.panel { display: none; padding: 10px; border-left: 3px solid #888; }
.section-title { margin-top: 30px; }
.controls { margin: 15px 0; }
table { border-collapse: collapse; margin-bottom: 20px; }
td, th { padding: 5px 10px; border: 1px solid #888; }
</style>

<script>
function togglePanel(id) {
  var p = document.getElementById(id);
  if (!p) return;
  p.style.display = (p.style.display === "block") ? "none" : "block";
}

function setMode(mode) {
  var mSec = document.getElementById('section-mismatch');
  var aSec = document.getElementById('section-all');
  if (!mSec || !aSec) return;
  if (mode === 'only_mismatches') {
    mSec.style.display = 'block';
    aSec.style.display = 'none';
  } else if (mode === 'all_blocks') {
    mSec.style.display = 'none';
    aSec.style.display = 'block';
  } else {
    mSec.style.display = 'block';
    aSec.style.display = 'block';
  }
}

function filterBlocks() {
  var select = document.getElementById('fieldFilter');
  var value = select.value;
  var accs = document.querySelectorAll('.accordion');
  accs.forEach(function(a) {
    var fields = a.getAttribute('data-fields') || '';
    if (!value || fields.includes(value)) {
      a.style.display = 'block';
    } else {
      a.style.display = 'none';
      var panelId = a.getAttribute('data-panel-id');
      var panel = document.getElementById(panelId);
      if (panel) panel.style.display = 'none';
    }
  });
}
</script>
""")
    html.append("</head><body>")

    html.append("<h1>AAPS Parity Report — Interactive</h1>")

    # Summary table
    mism = summary["mismatches"]
    total = summary["total_blocks"]

    html.append("<h2>Summary</h2>")
    html.append("<table>")
    html.append("<tr><th>Field</th><th>Mismatches</th></tr>")
    for field, count in mism.items():
        color = "#ffcccc" if count > 0 else "#ccffcc"
        html.append(f"<tr style='background:{color}'><td>{field}</td><td>{count}</td></tr>")
    html.append(f"<tr><td><b>Total blocks</b></td><td>{total}</td></tr>")
    html.append("</table>")

    # Controls
    html.append("""
<div class="controls">
  <button onclick="setMode('only_mismatches')">Only mismatches</button>
  <button onclick="setMode('all_blocks')">All blocks</button>
  <button onclick="setMode('both')">Both sections</button>
  &nbsp;&nbsp;
  <label>Filter by field: </label>
  <select id="fieldFilter" onchange="filterBlocks()">
    <option value="">All</option>
    <option value="eventualBG">eventualBG</option>
    <option value="variable_sens">variable_sens</option>
    <option value="minPredBG">minPredBG</option>
    <option value="minGuardBG">minGuardBG</option>
    <option value="insulinReq">insulinReq</option>
    <option value="rate">rate</option>
    <option value="duration">duration</option>
    <option value="smb">smb</option>
  </select>
</div>
""")

    # Heatmap
    html.append("<h2 class='section-title'>Mismatch Heatmap</h2>")
    html.append(build_heatmap(results))

    # Mismatch section
    html.append("<div id='section-mismatch'>")
    html.append("<h2 class='section-title'>Mismatch Blocks (predBG differences)</h2>")

    if not mismatch_blocks:
        html.append("<p>No mismatches found (predBGs_max_diff == 0 for all blocks).</p>")
    else:
        for r in mismatch_blocks:
            idx = r["idx"]
            aaps_block = load_inputs_block(idx)
            mismatch_fields = get_block_mismatch_fields(r)
            fields_str = ", ".join(mismatch_fields) if mismatch_fields else "none"
            panel_id = f"m_panel_{idx}"

            html.append(
                f"<div class='accordion' onclick=\"togglePanel('{panel_id}')\" "
                f"data-fields=\"{fields_str}\" data-panel-id=\"{panel_id}\">"
                f"Mismatch block {idx} (fields: {fields_str})"
                f"</div>"
            )
            html.append(f"<div class='panel' id='{panel_id}'>")
            html.append(build_predbg_plot(r, aaps_block))
            html.append("</div>")

    html.append("</div>")  # end mismatch section

    # All blocks section
    html.append("<div id='section-all'>")
    html.append("<h2 class='section-title'>All Blocks (predBG AAPS vs Python)</h2>")

    for r in all_blocks:
        idx = r["idx"]
        aaps_block = load_inputs_block(idx)
        mismatch_fields = get_block_mismatch_fields(r)
        fields_str = ", ".join(mismatch_fields) if mismatch_fields else "none"
        panel_id = f"a_panel_{idx}"

        html.append(
            f"<div class='accordion' onclick=\"togglePanel('{panel_id}')\" "
            f"data-fields=\"{fields_str}\" data-panel-id=\"{panel_id}\">"
            f"Block {idx} (fields: {fields_str})"
            f"</div>"
        )
        html.append(f"<div class='panel' id='{panel_id}'>")
        html.append(build_predbg_plot(r, aaps_block))
        html.append("</div>")

    html.append("</div>")  # end all blocks section

    # Auto mode
    if not mismatch_blocks:
        html.append("""
<script>
window.addEventListener('load', function() {
  setMode('all_blocks');
});
</script>
""")
    else:
        html.append("""
<script>
window.addEventListener('load', function() {
  setMode('both');
});
</script>
""")

    html.append("</body></html>")

    OUT_HTML.write_text("\n".join(html), encoding="utf-8")
    print(f"Interactive report saved to: {OUT_HTML}")


if __name__ == "__main__":
    main()
