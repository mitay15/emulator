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

                rt_in = inputs.get("rt") or {}
                row = {
                    "idx": idx,
                    "ts_s": ts_s,
                    "zip_name": zip_name,
                    # inputs["rt"] is normalized: eventual_bg is mmol/L already
                    "aaps_eventual": rt_in.get("eventual_bg") if rt_in.get("eventual_bg") is not None else 0.0,
                    "py_eventual": result.eventualBG,
                    "aaps_rate": rt_in.get("rate"),
                    "py_rate": result.rate,
                    "aaps_duration": rt_in.get("duration"),
                    "py_duration": result.duration,
                    "aaps_insreq": rt_in.get("insulin_req"),
                    "py_insreq": result.insulinReq,
                }

                all_rows.append(row)
                all_blocks.append(b)
                all_inputs.append(inputs)
                idx += 1

    return all_rows, all_blocks, all_inputs

def run_compare_on_log(log_path, out_csv_path):
    """
    Обрабатывает один обычный лог-файл (НЕ ZIP).
    Пишет CSV с результатами сравнения.
    """
    all_rows = []
    all_blocks = []
    all_inputs = []

    # Загружаем блоки RT из файла
    blocks = load_log_blocks(log_path)

    idx = 0
    for b in blocks:
        inputs = build_inputs(b)
        if not inputs:
            continue

        # Запуск алгоритма
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

        # timestamp
        ts_m = re.search(r"timestamp=(\d+)", b["rt"])
        ts_s = int(int(ts_m.group(1)) / 1000) if ts_m else 0

        rt_in = inputs.get("rt") or {}
        row = {
            "idx": idx,
            "ts_s": ts_s,
            "zip_name": os.path.basename(log_path),
            "aaps_eventual": rt_in.get("eventual_bg") if rt_in.get("eventual_bg") is not None else 0.0,
            "py_eventual": result.eventualBG,
            "aaps_rate": rt_in.get("rate"),
            "py_rate": result.rate,
            "aaps_duration": rt_in.get("duration"),
            "py_duration": result.duration,
            "aaps_insreq": rt_in.get("insulin_req"),
            "py_insreq": result.insulinReq,
        }

        all_rows.append(row)
        all_blocks.append(b)
        all_inputs.append(inputs)
        idx += 1

    # Записываем CSV
    import csv
    with open(out_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)

    return all_rows, all_blocks, all_inputs
