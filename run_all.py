# run_all.py
from pathlib import Path
import subprocess
import webbrowser

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "data" / "reports" / "html" / "parity_report_interactive.html"


def run(cmd: str):
    print(f"\n>>> {cmd}")
    subprocess.run(cmd, shell=True, check=True)


def main():
    # Полный пайплайн: compare_runner + heatmap + predBG diff + интерактивный HTML
    run("python -m aaps_emulator.tools.run_full_report --fast --open")

    if HTML.exists():
        print(f"\nOpening report: {HTML}")
        webbrowser.open(HTML.as_uri())
    else:
        print(f"\nReport not found at: {HTML}")


if __name__ == "__main__":
    main()
