# aaps_emulator/runner/compare_runner.py
from __future__ import annotations
from typing import Any, List, Dict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import logging
import time
import json
import traceback
import os
from dataclasses import is_dataclass, asdict

from aaps_emulator.runner.load_logs import load_logs
from aaps_emulator.runner.build_inputs import build_inputs_from_block
from aaps_emulator.core.autoisf_pipeline import run_autoisf_pipeline

logger = logging.getLogger("autoisf")


class C:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"


def _detect_timezone(ts: int) -> timezone:
    try:
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return dt.tzinfo or timezone.utc
    except Exception:
        return timezone.utc


def _extract_aaps_result_from_objs(objs):
    if isinstance(objs, dict) and objs.get("__type__") == "RT":
        return objs
    if isinstance(objs, list):
        for o in objs:
            if isinstance(o, dict) and o.get("__type__") == "RT":
                return o
    if isinstance(objs, dict):
        for v in objs.values():
            if isinstance(v, dict) and v.get("__type__") == "RT":
                return v
    return {}


def _progress_bar(current, total, start_time, bar_len=40):
    elapsed = time.time() - start_time
    rate = current / elapsed if elapsed > 0 else 0
    eta = (total - current) / rate if rate > 0 else 0

    filled = int(bar_len * current / total)
    bar = "█" * filled + "-" * (bar_len - filled)

    print(
        f"\r{C.CYAN}[{bar}] {current}/{total} "
        f"({current/total*100:5.1f}%) | "
        f"ETA: {eta:5.1f}s | "
        f"Speed: {rate:5.1f} blk/s{C.END}",
        end="",
        flush=True,
    )


def _serialize(obj):
    try:
        if obj is None:
            return None
        if isinstance(obj, (datetime,)):
            return obj.isoformat()
        if is_dataclass(obj):
            return asdict(obj)
        if hasattr(obj, "__dict__"):
            return {k: _serialize(v) for k, v in vars(obj).items()}
        if isinstance(obj, dict):
            return {k: _serialize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_serialize(v) for v in obj]
        return obj
    except Exception:
        return str(obj)


def _dump_error_block(idx, block_objs, exc, stage):
    try:
        cache_dir = Path(__file__).parent.parent / "data" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        out = cache_dir / f"error_block_{stage}_{idx}.json"

        with out.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "error": str(exc),
                    "stage": stage,
                    "trace": traceback.format_exc(),
                    "block": _serialize(block_objs),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        logger.error(f"Сохранён дамп ошибки: {out}")

    except Exception as e:
        logger.error(f"Не удалось сохранить дамп ошибки: {e}")


def dump_mismatch_json(output_dir: str, filename: str, data: Dict[str, Any]) -> None:
    """
    Создаёт папку output_dir (если нужно) и записывает data в JSON-файл filename.
    Использует ensure_ascii=False и отступ 2 для читаемости.
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # не ломаем основной прогон — логируем ошибку в stdout/stderr
        logger.error(f"Failed to write mismatch JSON {filename}: {e}")


def compare_logs(paths=None, fast: bool = False, return_stats: bool = False):
    # paths=None → data/logs
    if not paths:
        default_dir = Path("data/logs")
        paths = (
            list(default_dir.rglob("*.json"))
            + list(default_dir.rglob("*.zip"))
            + list(default_dir.rglob("*.log"))
        )

    start_time = time.time()
    logger.info(f"Начало обработки логов: {paths}")

    all_parsed: List[Any] = []
    for p in paths:
        parsed = load_logs(p)
        logger.info(f"Загружено {len(parsed)} объектов из {p}")
        all_parsed.extend(parsed)

    # собираем AutoISF-блоки
    blocks: List[List[dict]] = []
    i = 0
    n = len(all_parsed)

    while i < n:
        obj = all_parsed[i]
        if isinstance(obj, dict) and obj.get("__type__") == "GlucoseStatusAutoIsf":
            block_objs = [obj]
            j = i + 1
            while j < n:
                block_objs.append(all_parsed[j])
                if isinstance(all_parsed[j], dict) and all_parsed[j].get("__type__") == "RT":
                    break
                j += 1
            blocks.append(block_objs)
            i = j + 1
        else:
            i += 1

    if not blocks:
        logger.error("Нет AutoISF-блоков.")
        raise ValueError("Нет AutoISF-блоков.")

    total = len(blocks)
    print(f"Обработка {total} AutoISF блоков...")

    mismatch_stats = {
        "eventualBG": 0,
        "variable_sens": 0,
        "min_pred_bg": 0,
        "min_guard_bg": 0,
        "insulinReq": 0,
        "rate": 0,
        "duration": 0,
        "smb": 0,
    }

    cache_dir = Path(__file__).parent.parent / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    rows: List[dict] = []
    ns_results: List[SimpleNamespace] = []

    for idx, block_objs in enumerate(blocks, start=1):
        aaps_res = _extract_aaps_result_from_objs(block_objs) or {}
        ts = aaps_res.get("timestamp") or block_objs[0].get("date") or 0
        tz = _detect_timezone(ts)

        try:
            inputs = build_inputs_from_block(block_objs)
        except Exception as exc:
            logger.error(f"[{idx}] Ошибка build_inputs: {exc}")
            _dump_error_block(idx, block_objs, exc, stage="build_inputs")
            continue

        try:
            variable_sens, pred, dosing = run_autoisf_pipeline(inputs)
        except Exception as exc:
            logger.error(f"[{idx}] Ошибка pipeline: {exc}")
            _dump_error_block(idx, block_objs, exc, stage="pipeline")
            continue

        # AAPS значения
        aaps_eventual = aaps_res.get("eventualBG")
        aaps_min_pred = aaps_res.get("minPredBG")
        aaps_min_guard = aaps_res.get("minGuardBG")
        aaps_var_sens = aaps_res.get("variable_sens")
        aaps_insulinReq = aaps_res.get("insulinReq")
        aaps_rate = aaps_res.get("rate")
        aaps_duration = aaps_res.get("duration")
        aaps_smb = aaps_res.get("smb")

        # Python значения
        py_eventual = getattr(pred, "eventual_bg", None)
        py_min_pred = getattr(pred, "min_pred_bg", None)
        py_min_guard = getattr(pred, "min_guard_bg", None)
        py_var_sens = variable_sens
        py_insulinReq = getattr(dosing, "insulinReq", None)
        py_rate = getattr(dosing, "rate", None)
        py_duration = getattr(dosing, "duration", None)
        py_smb = getattr(dosing, "smb", None)

        mismatch = False

        def _cmp(a, b, tol=0.5):
            if a is None or b is None:
                return False
            try:
                return abs(float(a) - float(b)) > tol
            except Exception:
                return a != b

        if _cmp(aaps_eventual, py_eventual):
            mismatch_stats["eventualBG"] += 1
            mismatch = True

        if _cmp(aaps_var_sens, py_var_sens, tol=0.01):
            mismatch_stats["variable_sens"] += 1
            mismatch = True

        if _cmp(aaps_min_pred, py_min_pred):
            mismatch_stats["min_pred_bg"] += 1
            mismatch = True

        if _cmp(aaps_min_guard, py_min_guard):
            mismatch_stats["min_guard_bg"] += 1
            mismatch = True

        if _cmp(aaps_insulinReq, py_insulinReq):
            mismatch_stats["insulinReq"] += 1
            mismatch = True

        if _cmp(aaps_rate, py_rate):
            mismatch_stats["rate"] += 1
            mismatch = True

        if _cmp(aaps_duration, py_duration):
            mismatch_stats["duration"] += 1
            mismatch = True

        if _cmp(aaps_smb, py_smb):
            mismatch_stats["smb"] += 1
            mismatch = True

        row = {
            "idx": idx,
            "timestamp": ts,
            "eventualBG_aaps": aaps_eventual,
            "eventualBG_py": py_eventual,
            "variable_sens_aaps": aaps_var_sens,
            "variable_sens_py": py_var_sens,
            "minPredBG_aaps": aaps_min_pred,
            "minPredBG_py": py_min_pred,
            "minGuardBG_aaps": aaps_min_guard,
            "minGuardBG_py": py_min_guard,
            "insulinReq_aaps": aaps_insulinReq,
            "insulinReq_py": py_insulinReq,
            "rate_aaps": aaps_rate,
            "rate_py": py_rate,
            "duration_aaps": aaps_duration,
            "duration_py": py_duration,
            "smb_aaps": aaps_smb,
            "smb_py": py_smb,
        }
        rows.append(row)

        ns_results.append(SimpleNamespace(**row))

        if mismatch:
            try:
                out = cache_dir / f"mismatch_block_{idx}.json"
                with out.open("w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "index": idx,
                            "timestamp": ts,
                            "row": _serialize(row),
                            "inputs": {
                                "glucose_status": _serialize(inputs.glucose_status),
                                "current_temp": _serialize(inputs.current_temp),
                                "iob_data_array": _serialize(inputs.iob_data_array),
                                "profile": _serialize(inputs.profile),
                                "autosens": _serialize(inputs.autosens),
                                "meal": _serialize(inputs.meal),
                            },
                            "pred": _serialize(pred) if 'pred' in locals() else None,
                            "variable_sens_py": _serialize(variable_sens) if 'variable_sens' in locals() else None,
                            "dosing": _serialize(dosing) if 'dosing' in locals() else None,
                            "autoisf_debug": getattr(pred, "autoisf_debug", None) if 'pred' in locals() else None,
                            "aaps_rt": _serialize(aaps_res),
                            "block": _serialize(block_objs),
                        },
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
                logger.warning(f"Mismatch saved: {out}")
            except Exception as e:
                logger.error(f"Не удалось сохранить mismatch-блок: {e}")

        _progress_bar(idx, total, start_time)

    print()
    logger.info(f"Обработка завершена. Блоков: {total}")

    if return_stats:
        return {
            "total_blocks": total,
            "mismatches": mismatch_stats,
            "results": rows,
        }

    return ns_results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compare AAPS logs with Python AutoISF emulator (pipeline)")
    parser.add_argument("--log", type=str, help="Path to AAPS log file or directory", default=None)
    parser.add_argument("--fast", action="store_true", help="Fast mode (reserved, not used yet)")
    args = parser.parse_args()

    if args.log:
        paths = [args.log]
    else:
        default_dir = Path(__file__).parent.parent / "data" / "logs"
        paths = (
            list(default_dir.rglob("*.json"))
            + list(default_dir.rglob("*.zip"))
            + list(default_dir.rglob("*.log"))
        )

    if not paths:
        print("Нет логов для сравнения. Укажите путь через --log или положите JSON/ZIP/LOG в data/logs/")
    else:
        compare_logs(paths, fast=args.fast)
