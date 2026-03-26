# tools/run_full_report.py
from __future__ import annotations
import argparse
import time
import webbrowser
import json
import importlib
from multiprocessing import Pool
from pathlib import Path
import subprocess

from aaps_emulator.tools import plot_predbg_diff as plot_mod

ROOT = Path(__file__).parent.parent
LOG_FILE = ROOT / "data" / "reports" / "full_report.log"

if importlib.util.find_spec("plotly") is None:
    print("\nERROR: Plotly is not installed.")
    print("Install it with: pip install plotly")
    raise SystemExit

# --- Auto-check for Plotly ---
try:
    pass
except ImportError:
    print("\nERROR: Plotly is not installed.")
    print("Install it with:\n")
    print("    pip install plotly==5.22.0\n")
    print("Or install all dependencies:\n")
    print("    pip install -r requirements.txt\n")
    exit(1)


def log(msg: str):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg)


def run_compare_runner(fast: bool):
    cmd = "python -m aaps_emulator.runner.compare_runner --report"
    if fast:
        cmd += " --fast"

    start = time.time()
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    log(proc.stdout)
    log(proc.stderr)
    log(f"compare_runner duration: {time.time() - start:.2f}s")

    if proc.returncode != 0:
        raise RuntimeError("compare_runner failed")


def build_heatmap():
    start = time.time()
    cmd = "python -m aaps_emulator.tools.heatmap_diff"
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    log(proc.stdout)
    log(proc.stderr)
    log(f"heatmap duration: {time.time() - start:.2f}s")


def process_one_mismatch(args):
    path, out_dir, use_cache = args

    out_path = out_dir / (path.stem + ".png")

    if use_cache and out_path.exists():
        return f"SKIP (cached): {path.name}"

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return f"SKIP (bad json): {path.name}"

    if not data.get("predBGs_aaps") and not data.get("predBGs_py"):
        return f"SKIP (no predBGs): {path.name}"

    try:
        plot_mod.plot_predbg_diff(
            data.get("predBGs_aaps") or [],
            data.get("predBGs_py") or [],
            data.get("predBGs_diff") or data.get("predBGs_diffs"),
            out_path,
            title=f"Mismatch block {path.stem}",
            show_diff=True,
        )
        return f"OK: {path.name}"
    except Exception as e:
        return f"ERROR {path.name}: {e}"


def build_predbg_diffs(limit: int, workers: int, use_cache: bool):
    cache_dir = ROOT / "data" / "cache"
    out_dir = ROOT / "data" / "reports" / "predbg_diff"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(cache_dir.glob("mismatch_block_*.json"))
    if limit:
        files = files[:limit]

    log(f"Processing {len(files)} mismatch blocks with {workers} workers...")

    args = [(f, out_dir, use_cache) for f in files]

    start = time.time()
    with Pool(workers) as pool:
        for res in pool.imap_unordered(process_one_mismatch, args):
            log(res)

    log(f"predbg diffs duration: {time.time() - start:.2f}s")


def build_html():
    start = time.time()
    cmd = "python -m aaps_emulator.tools.generate_html_report_interactive"
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    log(proc.stdout)
    log(proc.stderr)
    log(f"html duration: {time.time() - start:.2f}s")


def main():
    parser = argparse.ArgumentParser(description="Full AAPS parity pipeline")
    parser.add_argument("--fast", action="store_true", help="Fast compare_runner")
    parser.add_argument("--open", action="store_true", help="Open HTML report")
    parser.add_argument("--limit", type=int, default=0, help="Limit mismatch plots")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers")
    parser.add_argument("--nocache", action="store_true", help="Disable cache")
    args = parser.parse_args()

    LOG_FILE.unlink(missing_ok=True)
    log("=== FULL PIPELINE START ===")

    run_compare_runner(args.fast)
    build_heatmap()
    build_predbg_diffs(args.limit, args.workers, not args.nocache)
    build_html()

    html_path = ROOT / "data" / "reports" / "html" / "parity_report_interactive.html"
    log(f"HTML report: {html_path}")

    if args.open:
        webbrowser.open(html_path.as_uri())

    log("=== FULL PIPELINE DONE ===")


if __name__ == "__main__":
    main()
