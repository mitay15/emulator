# aaps_emulator/runner/compare_runner.py
from __future__ import annotations

import json
import logging
import os
import time
import traceback
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, cast

from core.autoisf_pipeline import run_autoisf_pipeline
from runner.build_inputs import build_inputs_from_block
from runner.load_logs import load_logs


logger = logging.getLogger("autoisf")
logging.getLogger("autoisf").setLevel(logging.WARNING)


class C:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"


def _detect_timezone(ts: int) -> timezone:
    try:
        # создаём datetime, но возвращаем гарантированно timezone
        datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return timezone.utc
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

def compute_metrics(aaps_list, py_list):
    """Возвращает MAE, RMSE, max_diff и список diff’ов."""
    # Жёсткая защита от None и пустых входов
    if not aaps_list or not py_list:
        return {
            "mae": 0.0,
            "rmse": 0.0,
            "max_diff": 0.0,
            "diffs": [],
        }

    diffs = []
    for a, b in zip(aaps_list, py_list):
        if a is None or b is None:
            diffs.append(None)
        else:
            diffs.append(float(b) - float(a))

    clean = [abs(d) for d in diffs if d is not None]

    if not clean:
        return {
            "mae": 0.0,
            "rmse": 0.0,
            "max_diff": 0.0,
            "diffs": diffs,
        }

    mae = sum(clean) / len(clean)
    rmse = (sum(d * d for d in clean) / len(clean)) ** 0.5
    max_diff = max(clean)

    return {
        "mae": mae,
        "rmse": rmse,
        "max_diff": max_diff,
        "diffs": diffs,
    }

def is_fallback_rt(aaps_rt: dict) -> bool:
    if not aaps_rt:
        return True

    # 1. predBGs отсутствуют полностью → fallback
    preds = aaps_rt.get("predBGs")
    if preds is None:
        return True

    # 2. Если ВСЕ ветки отсутствуют → fallback
    if not any(preds.get(k) for k in ("IOB", "COB", "UAM")):
        return True

    # 3. minPredBG/minGuardBG могут отсутствовать — это НЕ fallback
    #    поэтому не проверяем

    # 4. rate/duration могут быть None — это НЕ fallback
    #    поэтому не проверяем

    # 5. consoleError — fallback только если есть явные аварии
    errors = aaps_rt.get("consoleError") or []
    for line in errors:
        if "Parabolic fit" in line or "extrapolates" in line:
            return True

    return False


def compare_logs(paths=None, fast: bool = False, return_stats: bool = False):
    # Тестовый режим — когда return_stats=True
    test_mode = return_stats

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
        source_log_path = str(p)
        logger.info(f"Загружено {len(parsed)} объектов из {p}")

        # ← ДОБАВЛЯЕМ ПУТЬ К ЛОГУ В КАЖДЫЙ ОБЪЕКТ
        for obj in parsed:
            if isinstance(obj, dict):
                obj["_log_path"] = source_log_path

                # Добавляем idx из имени файла clean-блока
                if test_mode:
                    fname = os.path.basename(source_log_path)
                    if fname.startswith("block_") and fname.endswith(".json"):
                        try:
                            external_idx = int(fname[6:-5])
                            obj["idx"] = external_idx
                        except Exception:
                            pass


        all_parsed.extend(parsed)

    # собираем AutoISF-блоки
    blocks: List[List[dict]] = []
    i = 0
    n = len(all_parsed)

    while i < n:
        obj = all_parsed[i]
        if isinstance(obj, dict) and obj.get("__type__") == "GlucoseStatusAutoIsf":
            block_objs = [obj]  # _log_path уже есть
            j = i + 1
            while j < n:
                next_obj = all_parsed[j]
                block_objs.append(next_obj)  # _log_path уже есть
                if (
                    isinstance(all_parsed[j], dict)
                    and all_parsed[j].get("__type__") == "RT"
                ):
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
    if not return_stats:
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

    # Если return_stats=True → тестовый режим
    test_mode = return_stats

    for local_idx, block_objs in enumerate(blocks, start=1):
        # ---------------------------------------------------------
        # SAVE CLEAN BLOCKS (block_objs) IF REQUESTED
        # ---------------------------------------------------------
        if args.extract_clean:
            clean_dir = Path("data") / "clean"
            clean_dir.mkdir(parents=True, exist_ok=True)

            clean_path = clean_dir / f"block_{local_idx:05d}.json"
            with clean_path.open("w", encoding="utf-8") as f:
                json.dump(block_objs, f, ensure_ascii=False, indent=2)

        idx: int = local_idx

        if test_mode:
            raw_idx = block_objs[0].get("idx")
            if isinstance(raw_idx, int):
                idx = cast(int, raw_idx)

        aaps_res = _extract_aaps_result_from_objs(block_objs) or {}
        fallback = is_fallback_rt(aaps_res)
        ts_raw = aaps_res.get("timestamp")
        if not isinstance(ts_raw, int):
            ts_raw = block_objs[0].get("date")
            if not isinstance(ts_raw, int):
                ts_raw = 0
        ts: int = ts_raw

        tz = _detect_timezone(ts)

        try:
            inputs = build_inputs_from_block(block_objs)
        except Exception as exc:
            logger.error(f"[{idx}] Ошибка build_inputs: {exc}")
            _dump_error_block(idx, block_objs, exc, stage="build_inputs")
            continue

        if test_mode:
            # Тестовый режим — НЕ запускаем pipeline
            variable_sens = aaps_res.get("variable_sens")
            pred = SimpleNamespace(
                eventual_bg=aaps_res.get("eventualBG"),
                min_pred_bg=aaps_res.get("minPredBG"),
                min_guard_bg=aaps_res.get("minGuardBG"),
                predBGs=(aaps_res.get("predBGs") or {}).get("UAM", []),
            )
            dosing = SimpleNamespace(
                insulinReq=aaps_res.get("insulinReq"),
                rate=aaps_res.get("rate"),
                duration=aaps_res.get("duration"),
                smb=aaps_res.get("smb"),
            )
        else:
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

        # predicted BG arrays
        # AAPS predBGs — это словарь, берём только UAM
        predBGs_dict = aaps_res.get("predBGs") or {}
        aaps_pred_list = predBGs_dict.get("UAM") or []

        # Python predBGs — гарантированно список
        py_pred_raw = getattr(pred, "predBGs", [])

        # если predBGs — словарь (старый формат), берём UAM
        if isinstance(py_pred_raw, dict):
            py_pred_list = py_pred_raw.get("UAM", []) or []
        # если None → пустой список
        elif py_pred_raw is None:
            py_pred_list = []
        # если список → оставляем
        else:
            py_pred_list = py_pred_raw

        # compute metrics
        pred_metrics = compute_metrics(aaps_pred_list, py_pred_list)

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
            "idx": int(idx),
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
            "predBGs_mae": pred_metrics["mae"],
            "predBGs_rmse": pred_metrics["rmse"],
            "predBGs_max_diff": pred_metrics["max_diff"],
            "fallback": fallback,
        }
        row["log_path"] = block_objs[0].get("_log_path")
        row["predBGs_aaps"] = aaps_pred_list
        row["predBGs_py"] = py_pred_list
        rows.append(row)


        ns_results.append(SimpleNamespace(**row))

        if fallback:
            # Пропускаем mismatch — AAPS был в аварийном режиме
            if not test_mode:
                _progress_bar(idx, total, start_time)

            continue

        if mismatch and not test_mode:
            try:
                out = cache_dir / f"mismatch_block_{idx}.json"

                with out.open("w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "index": idx,
                            "timestamp": ts,
                            "row": _serialize(row),
                            "predBGs_aaps": aaps_pred_list,
                            "predBGs_py": py_pred_list,
                            "predBGs_diff": pred_metrics["diffs"],
                            "predBGs_metrics": {
                                "mae": pred_metrics["mae"],
                                "rmse": pred_metrics["rmse"],
                                "max_diff": pred_metrics["max_diff"],
                            },
                            "inputs": {
                                "glucose_status": _serialize(inputs.glucose_status),
                                "current_temp": _serialize(inputs.current_temp),
                                "iob_data_array": _serialize(inputs.iob_data_array),
                                "profile": _serialize(inputs.profile),
                                "autosens": _serialize(inputs.autosens),
                                "meal": _serialize(inputs.meal),
                            },
                            "pred": _serialize(pred) if "pred" in locals() else None,
                            "variable_sens_py": (
                                _serialize(variable_sens)
                                if "variable_sens" in locals()
                                else None
                            ),
                            "dosing": (
                                _serialize(dosing) if "dosing" in locals() else None
                            ),
                            "autoisf_debug": (
                                getattr(pred, "autoisf_debug", None)
                                if "pred" in locals()
                                else None
                            ),
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

        if not test_mode:
            _progress_bar(idx, total, start_time)


    print()
    logger.info(f"Обработка завершена. Блоков: {total}")

    if not test_mode:
        # --- SAVE SUMMARY REPORT ---
        report_dir = Path("reports/compare")
        report_dir.mkdir(parents=True, exist_ok=True)

        # CSV
        csv_path = report_dir / "summary.csv"
        with csv_path.open("w", encoding="utf-8") as f:
            header = list(rows[0].keys())
            f.write(",".join(header) + "\n")
            for r in rows:
                f.write(",".join(str(r.get(h, "")) for h in header) + "\n")

        # JSON
        json_path = report_dir / "summary.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "total_blocks": total,
                    "mismatch_stats": mismatch_stats,
                    "rows": rows,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    if return_stats:
        return {
            "total_blocks": total,
            "mismatches": mismatch_stats,
            "results": rows,
        }

    return ns_results


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Compare AAPS logs with Python AutoISF emulator (pipeline)"
    )

    parser.add_argument(
        "--extract-clean",
        action="store_true",
        help="Extract clean AutoISF blocks into data/clean/"
    )

    parser.add_argument(
        "--log",
        type=str,
        help="Path to AAPS log file or directory",
        default=None,
    )

    parser.add_argument(
        "--fast",
        action="store_true",
        help="Fast mode (skip heavy checks)",
    )

    parser.add_argument(
        "--report",
        action="store_true",
        help="Return detailed stats instead of printing summary",
    )

    args = parser.parse_args()

    # Определяем пути
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
        print(
            "Нет логов для сравнения. Укажите путь через --log или положите JSON/ZIP/LOG в data/logs/"
        )
    else:
        compare_logs(paths, fast=args.fast, return_stats=args.report)
