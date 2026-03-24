# aaps_emulator/runner/compare_runner.py
from __future__ import annotations

import json
import logging
import time
import traceback
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

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
        f"({current/total*100:5.1f}%) | ETA: {eta:5.1f}s | Speed: {rate:5.1f} blk/s{C.END}",
        end="",
        flush=True,
    )


def _serialize(obj):
    try:
        if obj is None:
            return None
        if isinstance(obj, datetime):
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


def compute_metrics(aaps_list, py_list):
    if not aaps_list or not py_list:
        return {"mae": 0.0, "rmse": 0.0, "max_diff": 0.0, "diffs": []}

    diffs = []
    for a, b in zip(aaps_list, py_list):
        if a is None or b is None:
            diffs.append(None)
        else:
            diffs.append(float(b) - float(a))

    clean = [abs(d) for d in diffs if d is not None]

    if not clean:
        return {"mae": 0.0, "rmse": 0.0, "max_diff": 0.0, "diffs": diffs}

    mae = sum(clean) / len(clean)
    rmse = (sum(d * d for d in clean) / len(clean)) ** 0.5
    max_diff = max(clean)

    return {"mae": mae, "rmse": rmse, "max_diff": max_diff, "diffs": diffs}


def is_fallback_rt(aaps_rt: dict) -> bool:
    if not aaps_rt:
        return True

    preds = aaps_rt.get("predBGs")
    if preds is None:
        return True

    if not any(preds.get(k) for k in ("IOB", "COB", "UAM")):
        return True

    errors = aaps_rt.get("consoleError") or []
    for line in errors:
        if "Parabolic fit" in line or "extrapolates" in line:
            return True

    return False


# ============================================================
#   ОБРАБОТКА БЛОКОВ
# ============================================================

def _process_blocks(blocks, fast, return_stats, extract_clean):
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

    rows = []
    ns_results = []

    start_time = time.time()
    total = len(blocks)
    test_mode = return_stats

    for local_idx, block_objs in enumerate(blocks, start=1):

        # extract-clean работает только в normal‑режиме
        if extract_clean:
            clean_dir = Path(__file__).parent.parent / "data" / "clean"
            clean_dir.mkdir(parents=True, exist_ok=True)
            clean_path = clean_dir / f"block_{local_idx:05d}.json"
            with clean_path.open("w", encoding="utf-8") as f:
                json.dump(block_objs, f, ensure_ascii=False, indent=2)

        idx = local_idx

        aaps_res = _extract_aaps_result_from_objs(block_objs) or {}
        fallback = is_fallback_rt(aaps_res)

        ts_raw = aaps_res.get("timestamp")
        if not isinstance(ts_raw, int):
            ts_raw = block_objs[0].get("date", 0)
        ts = ts_raw

        try:
            inputs = build_inputs_from_block(block_objs)
        except Exception as exc:
            logger.error(f"[{idx}] Ошибка build_inputs: {exc}")
            _dump_error_block(idx, block_objs, exc, stage="build_inputs")
            continue

        if test_mode:
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

        aaps_eventual = aaps_res.get("eventualBG")
        aaps_min_pred = aaps_res.get("minPredBG")
        aaps_min_guard = aaps_res.get("minGuardBG")
        aaps_var_sens = aaps_res.get("variable_sens")
        aaps_insulinReq = aaps_res.get("insulinReq")
        aaps_rate = aaps_res.get("rate")
        aaps_duration = aaps_res.get("duration")
        aaps_smb = aaps_res.get("smb")

        py_eventual = getattr(pred, "eventual_bg", None)
        py_min_pred = getattr(pred, "min_pred_bg", None)
        py_min_guard = getattr(pred, "min_guard_bg", None)
        py_var_sens = variable_sens
        py_insulinReq = getattr(dosing, "insulinReq", None)
        py_rate = getattr(dosing, "rate", None)
        py_duration = getattr(dosing, "duration", None)
        py_smb = getattr(dosing, "smb", None)

        predBGs_dict = aaps_res.get("predBGs") or {}
        aaps_pred_list = predBGs_dict.get("UAM") or []

        py_pred_raw = getattr(pred, "predBGs", [])
        if isinstance(py_pred_raw, dict):
            py_pred_list = py_pred_raw.get("UAM", []) or []
        elif py_pred_raw is None:
            py_pred_list = []
        else:
            py_pred_list = py_pred_raw

        pred_metrics = compute_metrics(aaps_pred_list, py_pred_list)

        def _cmp(a, b, tol=0.5):
            if a is None or b is None:
                return False
            try:
                return abs(float(a) - float(b)) > tol
            except Exception:
                return a != b

        if _cmp(aaps_eventual, py_eventual):
            mismatch_stats["eventualBG"] += 1

        if _cmp(aaps_var_sens, py_var_sens, tol=0.01):
            mismatch_stats["variable_sens"] += 1

        if _cmp(aaps_min_pred, py_min_pred):
            mismatch_stats["min_pred_bg"] += 1

        if _cmp(aaps_min_guard, py_min_guard):
            mismatch_stats["min_guard_bg"] += 1

        if _cmp(aaps_insulinReq, py_insulinReq):
            mismatch_stats["insulinReq"] += 1

        if _cmp(aaps_rate, py_rate):
            mismatch_stats["rate"] += 1

        if _cmp(aaps_duration, py_duration):
            mismatch_stats["duration"] += 1

        if _cmp(aaps_smb, py_smb):
            mismatch_stats["smb"] += 1

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
            "predBGs_aaps": aaps_pred_list,
            "predBGs_py": py_pred_list,
        }

        rows.append(row)
        ns_results.append(SimpleNamespace(**row))

        if not test_mode:
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


# ============================================================
#   NORMAL MODE
# ============================================================

def compare_logs(paths=None, fast=False, return_stats=False, extract_clean=False):

    # CLEAN MODE
    if paths and all(str(p).endswith(".json") and "block_" in str(p) for p in paths):
        blocks = []
        for p in paths:
            with open(p, "r", encoding="utf-8") as f:
                block = json.load(f)
            if isinstance(block, list):
                blocks.append(block)

        if not blocks:
            raise ValueError("Не удалось загрузить clean-блоки.")

        print(f"Обработка {len(blocks)} clean-блоков...")
        return _process_blocks(blocks, fast, return_stats, extract_clean=False)

    # NORMAL MODE
    if not paths:
        default_dir = Path(__file__).parent.parent / "data" / "logs"
        paths = (
            list(default_dir.rglob("*.json"))
            + list(default_dir.rglob("*.zip"))
            + list(default_dir.rglob("*.log"))
        )

    all_parsed = []
    for p in paths:
        parsed = load_logs(p)
        for obj in parsed:
            if isinstance(obj, dict):
                obj["_log_path"] = str(p)
        all_parsed.extend(parsed)

    blocks = []
    i = 0
    n = len(all_parsed)

    while i < n:
        obj = all_parsed[i]
        if isinstance(obj, dict) and obj.get("__type__") == "GlucoseStatusAutoIsf":
            block = [obj]
            j = i + 1
            while j < n:
                block.append(all_parsed[j])
                if isinstance(all_parsed[j], dict) and all_parsed[j].get("__type__") == "RT":
                    break
                j += 1
            blocks.append(block)
            i = j + 1
        else:
            i += 1

    if not blocks:
        raise ValueError("Нет AutoISF-блоков.")

    print(f"Обработка {len(blocks)} AutoISF блоков...")
    return _process_blocks(blocks, fast, return_stats, extract_clean)


# ============================================================
#   CLI
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compare AAPS logs with Python AutoISF emulator")
    parser.add_argument("--log", default="data/logs")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--extract-clean", action="store_true")
    args = parser.parse_args()

    # Resolve paths
    paths = None
    if args.log:
        p = Path(args.log)
        if p.is_dir():
            clean_files = sorted(p.glob("block_*.json"))
            if clean_files:
                paths = clean_files
        if paths is None:
            paths = [args.log]

    if paths is None:
        default_dir = Path(__file__).parent.parent / "data" / "logs"
        paths = (
            list(default_dir.rglob("*.json"))
            + list(default_dir.rglob("*.zip"))
            + list(default_dir.rglob("*.log"))
        )

    result = compare_logs(
        paths,
        fast=args.fast,
        return_stats=args.report,
        extract_clean=args.extract_clean,
    )

    # SAVE REPORT
    if args.report:
        report_dir = Path(__file__).parent.parent / "data" / "report"
        report_dir.mkdir(parents=True, exist_ok=True)

        out = report_dir / "report.json"
        with out.open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\nОтчёт сохранён в: {out}")
