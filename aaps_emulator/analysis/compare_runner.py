# aaps_emulator/analysis/compare_runner.py
import csv
import os
import re
from pathlib import Path
from typing import Any

from aaps_emulator.config import LOGS_PATH
from aaps_emulator.core.autoisf_algorithm import determine_basal_autoisf
from aaps_emulator.parsing.inputs_builder import build_inputs
from aaps_emulator.parsing.log_loader import (
    extract_zip,
    find_all_zip_logs,
    load_log_blocks,
)


def _parse_timestamp_from_rt(rt_raw: str | None) -> int:
    """
    Извлекает timestamp (в секундах) из строки RT вида '... timestamp=1768389278274 ...'.
    Возвращает 0 если не найдено.
    """
    if not rt_raw:
        return 0
    m = re.search(r"timestamp=(\d+)", rt_raw)
    return int(int(m.group(1)) / 1000) if m else 0


def run_compare_on_all_logs(
    logs_dir: str | Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Обходит все ZIP-файлы в каталоге logs_dir, извлекает блоки логов и запускает
    determine_basal_autoisf для каждого блока в trace_mode=True.

    Возвращает кортеж (rows, blocks, inputs):
      - rows: список словарей с результатами и trace
      - blocks: список исходных блоков (как загружено из логов)
      - inputs: список нормализованных inputs (как возвращает build_inputs)
    """
    # По умолчанию используем константу LOGS_PATH
    if logs_dir is None:
        logs_dir = LOGS_PATH

    # find_all_zip_logs ожидает строковый путь
    zip_files = find_all_zip_logs(str(logs_dir))
    all_rows: list[dict[str, Any]] = []
    all_blocks: list[dict[str, Any]] = []
    all_inputs: list[dict[str, Any]] = []

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

                # timestamp from RT (if present)
                ts_s = _parse_timestamp_from_rt(b.get("rt"))
                # run algorithm with trace_mode to get detailed trace
                result, trace_steps = determine_basal_autoisf(
                    glucose_status=inputs["glucose_status"],
                    currenttemp=inputs.get("current_temp"),
                    iob_data_array=inputs.get("iob_array"),
                    profile=inputs.get("profile"),
                    autosens_data=inputs.get("autosens"),
                    meal_data=inputs.get("meal"),
                    rt=inputs.get("rt"),
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
                    trace_mode=True,
                )

                # Print trace (trace_steps already contains diagnostic.* and final.* keys)
                print("TRACE:")
                for name, value in trace_steps:
                    print(f"  {name}: {value}")
                print("  input.rt:", inputs.get("rt"))

                rt_in = inputs.get("rt") or {}
                row = {
                    "idx": idx,
                    "ts_s": ts_s,
                    "zip_name": zip_name,
                    "aaps_eventual": rt_in.get("eventual_bg") if rt_in.get("eventual_bg") is not None else 0.0,
                    "py_eventual": result.eventualBG,
                    "aaps_rate": rt_in.get("rate"),
                    "py_rate": result.rate,
                    "aaps_duration": rt_in.get("duration"),
                    "py_duration": result.duration,
                    "aaps_insreq": rt_in.get("insulin_req"),
                    "py_insreq": result.insulinReq,
                    "trace": trace_steps,
                }

                all_rows.append(row)
                all_blocks.append(b)
                all_inputs.append(inputs)
                idx += 1

    return all_rows, all_blocks, all_inputs


def run_compare_on_log(
    log_path: str, out_csv_path: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Обрабатывает один лог-файл (не ZIP), запускает determine_basal_autoisf для каждого блока,
    печатает trace и сохраняет результаты в CSV.
    """
    all_rows: list[dict[str, Any]] = []
    all_blocks: list[dict[str, Any]] = []
    all_inputs: list[dict[str, Any]] = []

    blocks = load_log_blocks(log_path)
    idx = 0
    for b in blocks:
        inputs = build_inputs(b)
        if not inputs:
            continue

        ts_s = _parse_timestamp_from_rt(b.get("rt"))

        result, trace_steps = determine_basal_autoisf(
            glucose_status=inputs["glucose_status"],
            currenttemp=inputs.get("current_temp"),
            iob_data_array=inputs.get("iob_array"),
            profile=inputs.get("profile"),
            autosens_data=inputs.get("autosens"),
            meal_data=inputs.get("meal"),
            rt=inputs.get("rt"),
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
            trace_mode=True,
        )

        # Print trace
        print("TRACE:")
        for name, value in trace_steps:
            print(f"  {name}: {value}")
        print("  input.rt:", inputs.get("rt"))

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
            "trace": trace_steps,
        }

        all_rows.append(row)
        all_blocks.append(b)
        all_inputs.append(inputs)
        idx += 1

    # Write CSV if requested
    if all_rows:
        with open(out_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_rows)

    return all_rows, all_blocks, all_inputs
