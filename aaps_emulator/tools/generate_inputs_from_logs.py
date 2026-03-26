# aaps_emulator/tools/generate_inputs_from_logs.py
import argparse
import json
from pathlib import Path
import glob

from aaps_emulator.runner.build_inputs import build_inputs_from_block
from aaps_emulator.runner.load_logs import load_logs

OUT_DIR = Path("data/cache")


def save_inputs_from_block(block, out_dir: Path):
    inputs_obj = build_inputs_from_block(block)
    ts = None
    try:
        gs = next(
            (
                o
                for o in block
                if isinstance(o, dict) and o.get("__type__") == "GlucoseStatusAutoIsf"
            ),
            None,
        )
        if gs and gs.get("date"):
            ts = gs.get("date")
    except Exception:
        ts = None
    if ts is None:
        rt = next(
            (o for o in block if isinstance(o, dict) and o.get("__type__") == "RT"),
            None,
        )
        ts = rt.get("timestamp") if rt and rt.get("timestamp") else "auto"
    out_name = f"inputs_before_algo_block_{ts}.json"
    out_path = out_dir / out_name
    if out_path.exists():
        print("Skip (exists):", out_path)
        return
    inputs_dump = {
        "inputs": {
            "glucose_status": (
                getattr(inputs_obj, "glucose_status").raw
                if getattr(inputs_obj, "glucose_status", None)
                else None
            ),
            "current_temp": (
                getattr(inputs_obj, "current_temp").raw
                if getattr(inputs_obj, "current_temp", None)
                else None
            ),
            "iob_data_array": [
                i.raw for i in getattr(inputs_obj, "iob_data_array", [])
            ],
            "profile": (
                getattr(inputs_obj, "profile").raw
                if getattr(inputs_obj, "profile", None)
                else None
            ),
            "autosens": (
                getattr(inputs_obj, "autosens").raw
                if getattr(inputs_obj, "autosens", None)
                else None
            ),
            "meal": (
                getattr(inputs_obj, "meal").raw
                if getattr(inputs_obj, "meal", None)
                else None
            ),
            "rt": getattr(inputs_obj, "rt", None) or None,
            "algorithm": getattr(inputs_obj, "rt", {}).get("algorithm"),
        },
        "block_index": ts,
    }

    algo = (
        inputs_dump["inputs"].get("algorithm")
        or inputs_dump["inputs"].get("rt", {}).get("algorithm")
    )
    inputs_dump["algorithm"] = algo

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(inputs_dump, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Saved:", out_path)


def main():
    parser = argparse.ArgumentParser()
    # поддерживаем позиционный аргумент и опцию --logs
    parser.add_argument("logs", nargs="?", default=None, help="path to logs dir or file (positional)")
    parser.add_argument("--logs", dest="logs_opt", default=None, help="path to logs dir or file (option)")
    parser.add_argument("--out", default=str(OUT_DIR), help="output dir")
    args = parser.parse_args()

    # выбрать значение аргумента: позиционный > --logs > дефолт
    logs_arg = args.logs if args.logs is not None else (args.logs_opt if args.logs_opt is not None else "data/logs")

    logs_path = Path(logs_arg)
    blocks = []

    # Если передали директорию — перебираем файлы в ней и вызываем load_logs для каждого
    if logs_path.is_dir():
        for p in sorted(logs_path.iterdir()):
            # пропускаем поддиректории
            if p.is_dir():
                continue
            try:
                blocks.extend(load_logs(str(p)))
            except ValueError:
                # пропускаем неподдерживаемые файлы
                continue
    else:
        # если передали шаблон (glob) — обработаем совпадения
        matched = glob.glob(logs_arg)
        if matched:
            for m in sorted(matched):
                try:
                    blocks.extend(load_logs(m))
                except ValueError:
                    continue
        else:
            # иначе пробуем как одиночный файл
            blocks = load_logs(logs_arg)

    print("Loaded blocks:", len(blocks))

    # Group by GlucoseStatusAutoIsf occurrences
    grouped = []
    current = []
    for obj in blocks:
        if isinstance(obj, dict) and obj.get("__type__") == "GlucoseStatusAutoIsf":
            if current:
                grouped.append(current)
            current = [obj]
        else:
            if current is None:
                current = []
            current.append(obj)
    if current:
        grouped.append(current)
    print("Grouped blocks:", len(grouped))

    out_dir = Path(args.out)
    for block in grouped:
        try:
            save_inputs_from_block(block, out_dir)
        except Exception as e:
            print("Error saving block:", e)


if __name__ == "__main__":
    main()
