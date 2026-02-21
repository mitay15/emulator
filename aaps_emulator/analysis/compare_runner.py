# aaps_emulator/analysis/compare_runner.py
import os
import re

from aaps_emulator.core.autoisf_algorithm import determine_basal_autoisf
from aaps_emulator.parsing.inputs_builder import build_inputs
from aaps_emulator.parsing.log_loader import (
    extract_zip,
    find_all_zip_logs,
    load_log_blocks,
)


def run_compare_on_all_logs(logs_dir="logs"):
    """
    Возвращает:
      rows: list of dict {
        idx, ts_s, zip_name, aaps_eventual, py_eventual, aaps_rate, py_rate,
        aaps_duration, py_duration, aaps_insreq, py_insreq
      }
      blocks: list of original blocks (same order)
      inputs: list of inputs (same order)
    """
    zip_files = find_all_zip_logs(logs_dir)
    all_rows = []
    all_blocks = []
    all_inputs = []

    idx = 0
    for zip_path in zip_files:
        zip_name = os.path.basename(zip_path)
        print(f"Processing ZIP: {zip_path}")
        files = extract_zip(zip_path, out_dir=os.path.dirname(zip_path))
        for f in files:
            blocks = load_log_blocks(f)
            for b in blocks:
                inputs = build_inputs(b)
                if not inputs:
                    continue

                # run algorithm directly to keep parity with previous runner
                result = determine_basal_autoisf(
                    glucose_status=inputs["glucose_status"],
                    currenttemp=inputs["current_temp"],
                    iob_data_array=inputs["iob_array"],
                    profile=inputs["profile"],
                    autosens_data=inputs["autosens"],
                    meal_data=inputs["meal"],
                    microBolusAllowed=False,
                    currentTime=0,
                    flatBGsDetected=False,
                    autoIsfMode=True,
                    loop_wanted_smb="none",
                    profile_percentage=100,
                    smb_ratio=0.5,
                    smb_max_range_extension=1.0,
                    iob_threshold_percent=100,
                    auto_isf_consoleError=[],
                    auto_isf_consoleLog=[],
                )

                # parse timestamp from RT line (ms -> s)
                ts_m = re.search(r"timestamp=(\d+)", b["rt"])
                ts_s = int(int(ts_m.group(1)) / 1000) if ts_m else 0

                row = {
                    "idx": idx,
                    "ts_s": ts_s,
                    "zip_name": zip_name,
                    "aaps_eventual": (inputs["rt"].get("eventualBG") or 0) / 18.0,
                    "py_eventual": result.eventualBG,
                    "aaps_rate": inputs["rt"].get("rate"),
                    "py_rate": result.rate,
                    "aaps_duration": inputs["rt"].get("duration"),
                    "py_duration": result.duration,
                    "aaps_insreq": inputs["rt"].get("insulinReq"),
                    "py_insreq": result.insulinReq,
                }

                all_rows.append(row)
                all_blocks.append(b)
                all_inputs.append(inputs)
                idx += 1

    return all_rows, all_blocks, all_inputs
