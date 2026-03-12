# aaps_emulator/run.py
from __future__ import annotations
import argparse
from pathlib import Path
import logging
import json

from aaps_emulator.runner.compare_runner import compare_logs
from aaps_emulator.runner.generate_report import save_csv
from aaps_emulator.visual.dashboard import build_dashboard
from aaps_emulator.runner.load_logs import load_logs


def setup_logging(base: Path):
    log_dir = base / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "autoisf.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", nargs="+", required=True)
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--csv", action="store_true")
    parser.add_argument("--fast", action="store_true", help="Быстрый режим (только eventualBG и insulinReq)")
    parser.add_argument("--dump-parsed", action="store_true", help="Save all parsed blocks to data/cache/parsed_blocks.json for debugging")
    args = parser.parse_args()

    base = Path(__file__).parent
    setup_logging(base)

    paths = [Path(p) for p in args.log]

    # --- dump parsed blocks when requested
    if args.dump_parsed:
        try:
            cache_dir = base / "data" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            parsed_all = []
            for p in paths:
                parsed_all.extend(load_logs(p))
            out = cache_dir / "parsed_blocks.json"
            with out.open("w", encoding="utf-8") as f:
                json.dump(parsed_all, f, ensure_ascii=False, indent=2)
            print(f"Parsed blocks dumped to {out}")
        except Exception as e:
            print(f"Failed to dump parsed blocks: {e}")
    # --- end dump parsed blocks

    results = compare_logs(paths, fast=args.fast)

    if args.csv:
        csv_path = base / "data" / "reports" / "autoisf_results.csv"
        save_csv(results, csv_path)
        print(f"CSV сохранён: {csv_path}")

    fig = build_dashboard(results)

    if args.html:
        out = base / "data" / "reports" / "autoisf_dashboard.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(out)
        print(f"HTML сохранён: {out}")
    else:
        fig.show()


if __name__ == "__main__":
    main()
