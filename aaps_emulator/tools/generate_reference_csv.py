# aaps_emulator/tools/generate_reference_csv.py
"""
Генерация reference CSV на основе текущих логов и текущего парсера/раннера.
Выходной CSV содержит колонки:
  idx,ts_s,aaps_eventual,aaps_rate,aaps_duration,aaps_insreq

Запуск (из корня проекта aaps_emulator):
  python tools/generate_reference_csv.py --out tests/reference_generated.csv --logs logs

Если возникнут ошибки импорта, запусти скрипт напрямую:
  python aaps_emulator/tools/generate_reference_csv.py --out aaps_emulator/tests/reference_generated.csv --logs logs
"""

import argparse
import csv
import os
import sys

from aaps_emulator.analysis.compare_runner import run_compare_on_all_logs

# Попытка корректного добавления корня проекта в sys.path, если запускаешь напрямую
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def generate(out_path, logs_dir):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    rows, blocks, inputs = run_compare_on_all_logs(logs_dir)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "idx",
                "ts_s",
                "aaps_eventual",
                "aaps_rate",
                "aaps_duration",
                "aaps_insreq",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r.get("idx", ""),
                    r.get("ts_s", ""),
                    r.get("aaps_eventual", ""),
                    r.get("aaps_rate", ""),
                    r.get("aaps_duration", ""),
                    r.get("aaps_insreq", ""),
                ]
            )

    print(f"Wrote {len(rows)} rows to {out_path}")
    # print a small sample
    for r in rows[:5]:
        print(r)


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--out", default="tests/reference_generated.csv", help="Output CSV path"
    )
    p.add_argument(
        "--logs", default="logs", help="Logs directory (relative to project root)"
    )
    args = p.parse_args()
    generate(args.out, args.logs)


if __name__ == "__main__":
    main()
