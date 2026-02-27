import json
from pathlib import Path

METRICS_PATH = Path("reports/last_run/metrics.json")
DASHBOARD_PATH = Path("reports/last_run/metrics_dashboard.html")


def build_dashboard():
    if not METRICS_PATH.exists():
        raise FileNotFoundError(f"Metrics file not found: {METRICS_PATH}")

    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>AAPS Emulator Metrics</title>
  <style>
    body {{ font-family: sans-serif; margin: 20px; }}
    h1 {{ margin-bottom: 0.2em; }}
    table {{ border-collapse: collapse; margin-top: 1em; }}
    th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: right; }}
    th {{ background: #f0f0f0; }}
  </style>
</head>
<body>
  <h1>AAPS Emulator — Metrics</h1>
  <p>Total points: {metrics.get("count", "n/a")}</p>
  <table>
    <tr><th>Metric</th><th>Value</th></tr>
    <tr><td>eventualBG MAE</td><td>{metrics.get("eventualBG_mae", "n/a")}</td></tr>
    <tr><td>eventualBG Max</td><td>{metrics.get("eventualBG_max", "n/a")}</td></tr>
    <tr><td>Rate MAE</td><td>{metrics.get("rate_mae", "n/a")}</td></tr>
    <tr><td>Rate Max</td><td>{metrics.get("rate_max", "n/a")}</td></tr>
  </table>
</body>
</html>
"""

    DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_PATH.write_text(html, encoding="utf-8")
    print("Dashboard saved to", DASHBOARD_PATH)


if __name__ == "__main__":
    build_dashboard()
