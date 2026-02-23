from pathlib import Path

REPORT_TXT = Path("aaps_emulator/tests/autoisf_report.txt")
PLOTS_DIR = Path("aaps_emulator/tests/plots")
HTML_OUT = Path("aaps_emulator/tests/autoisf_report.html")


def main():
    if not REPORT_TXT.exists():
        print("Report text not found:", REPORT_TXT)
        return

    text = REPORT_TXT.read_text(encoding="utf-8")

    html = f"""
<html>
<head>
<title>AutoISF Report</title>
<style>
body {{
    font-family: Arial, sans-serif;
    margin: 20px;
}}
pre {{
    background: #f0f0f0;
    padding: 10px;
    border-radius: 6px;
}}
img {{
    max-width: 100%;
    margin-bottom: 20px;
    border: 1px solid #ccc;
}}
</style>
</head>
<body>

<h1>AutoISF Python vs AAPS — Full Report</h1>

<h2>Summary</h2>
<pre>{text}</pre>

<h2>Plots</h2>
"""

    for img in ["rate_compare.png", "eventual_compare.png", "diff_eventual.png", "scatter_rate.png"]:
        img_path = PLOTS_DIR / img
        if img_path.exists():
            html += f"<h3>{img}</h3><img src='../plots/{img}' />"

    html += """
</body>
</html>
"""

    HTML_OUT.write_text(html, encoding="utf-8")
    print("HTML report written to:", HTML_OUT)


if __name__ == "__main__":
    main()
