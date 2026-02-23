# aaps_emulator/tools/inspect_idx.py
"""
Inspect inputs and AutoISF result for a single idx.
Usage:
  python -m aaps_emulator.tools.inspect_idx --idx 11
"""

import argparse

from aaps_emulator.analysis.compare_runner import run_compare_on_all_logs
from aaps_emulator.core.autoisf_algorithm import determine_basal_autoisf


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--idx", type=int, required=True)
    p.add_argument("--logs", default="aaps_emulator/logs")
    args = p.parse_args()

    rows, blocks, inputs = run_compare_on_all_logs(args.logs)

    for r, b, inp in zip(rows, blocks, inputs, strict=True):
        if r["idx"] == args.idx:
            print("ROW:", r)
            print("BLOCK (rt snippet):", {"rt": b.get("rt")})
            print("INPUT keys:", list(inp.keys()))

            print("glucose_status:", getattr(inp.get("glucose_status"), "__dict__", inp.get("glucose_status")))
            print("autosens:", getattr(inp.get("autosens"), "__dict__", inp.get("autosens")))
            print("iob_array len:", len(inp.get("iob_array") or []))
            print("profile:", getattr(inp.get("profile"), "__dict__", inp.get("profile")))

            errs = []
            logs = []
            res = determine_basal_autoisf(
                glucose_status=inp.get("glucose_status"),
                currenttemp=inp.get("current_temp"),
                iob_data_array=inp.get("iob_array"),
                profile=inp.get("profile"),
                autosens_data=inp.get("autosens"),
                meal_data=inp.get("meal"),
                rt=inp.get("rt"),
                auto_isf_consoleError=errs,
                auto_isf_consoleLog=logs,
            )

            print("AutoISF result:", res)
            print("Console logs:", logs)
            print("Console errors:", errs)
            return

    print("idx not found:", args.idx)


if __name__ == "__main__":
    main()
