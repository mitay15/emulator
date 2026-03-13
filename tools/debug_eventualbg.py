# tools/debug_eventualbg.py
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from core.autoisf_pipeline import run_autoisf_pipeline
from runner.build_inputs import build_inputs_from_block

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

THRESHOLD = -50


def load_csv():
    csv_path = Path("data/reports/autoisf_results.csv")
    if not csv_path.exists():
        raise SystemExit(
            "CSV report not found: aaps_emulator/data/reports/autoisf_results.csv"
        )
    df = pd.read_csv(csv_path)
    if "eventual_bg" in df.columns and "aaps_eventual_bg" in df.columns:
        df["diff_eventual_bg"] = df["eventual_bg"] - df["aaps_eventual_bg"]
    return df


def load_blocks():
    path = Path("data/cache/parsed_blocks.json")
    if not path.exists():
        raise SystemExit(
            "parsed_blocks.json not found. Run run.py with --dump-parsed first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def extract_autoisf_block(blocks, timestamp):
    """Find nearest GlucoseStatusAutoIsf by timestamp."""
    candidates = [b for b in blocks if b.get("__type__") == "GlucoseStatusAutoIsf"]
    if not candidates:
        return None
    return min(candidates, key=lambda b: abs(b.get("date", 0) - timestamp))


def find_neighbors(blocks, auto_block):
    """Collect surrounding objects for an AutoISF block."""
    idx = blocks.index(auto_block)

    result = {
        "glucose": auto_block,
        "temp": None,
        "iob": [],
        "profile": None,
        "autosens": None,
        "meal": None,
        "rt": None,
    }

    # scan forward until next GlucoseStatusAutoIsf
    for j in range(idx + 1, len(blocks)):
        b = blocks[j]
        t = b.get("__type__")

        if t == "GlucoseStatusAutoIsf":
            break

        if t == "CurrentTemp":
            result["temp"] = b
        elif t == "IobTotal":
            result["iob"].append(b)
        elif t == "OapsProfileAutoIsf":
            result["profile"] = b
        elif t == "AutosensResult":
            result["autosens"] = b
        elif t == "MealData":
            result["meal"] = b
        elif t == "RT":
            result["rt"] = b

    return result


def build_profile(block):
    return SimpleNamespace(
        min_bg=block.get("min_bg"),
        max_bg=block.get("max_bg"),
        target_bg=block.get("target_bg"),
        sens=block.get("sens"),
        variable_sens=block.get("variable_sens"),
        current_basal=block.get("current_basal"),
        autoISF_min=block.get("autoISF_min"),
        autoISF_max=block.get("autoISF_max"),
        autoISF_version=block.get("autoISF_version"),
        enable_autoISF=block.get("enable_autoISF"),
        smb_max_range_extension=block.get("smb_max_range_extension"),
        smb_delivery_ratio=block.get("smb_delivery_ratio"),
        smb_delivery_ratio_min=block.get("smb_delivery_ratio_min"),
        smb_delivery_ratio_max=block.get("smb_delivery_ratio_max"),
        smb_delivery_ratio_bg_range=block.get("smb_delivery_ratio_bg_range"),
        iob_threshold_percent=block.get("iob_threshold_percent"),
        max_iob=block.get("max_iob"),
        profile_percentage=block.get("profile_percentage"),
        max_daily_basal=block.get("max_daily_basal"),
        max_basal=block.get("max_basal"),
        autosens_adjust_targets=block.get("autosens_adjust_targets"),
        max_daily_safety_multiplier=block.get("max_daily_safety_multiplier"),
        current_basal_safety_multiplier=block.get("current_basal_safety_multiplier"),
        high_temptarget_raises_sensitivity=block.get(
            "high_temptarget_raises_sensitivity"
        ),
        low_temptarget_lowers_sensitivity=block.get(
            "low_temptarget_lowers_sensitivity"
        ),
        sensitivity_raises_target=block.get("sensitivity_raises_target"),
        resistance_lowers_target=block.get("resistance_lowers_target"),
        adv_target_adjustments=block.get("adv_target_adjustments"),
        exercise_mode=block.get("exercise_mode"),
        half_basal_exercise_target=block.get("half_basal_exercise_target"),
        carb_ratio=block.get("carb_ratio"),
        maxCOB=block.get("maxCOB"),
        remainingCarbsCap=block.get("remainingCarbsCap"),
        carbsReqThreshold=block.get("carbsReqThreshold"),
        enableUAM=block.get("enableUAM"),
        A52_risk_enable=block.get("A52_risk_enable"),
        SMBInterval=block.get("SMBInterval"),
        enableSMB_with_COB=block.get("enableSMB_with_COB"),
        enableSMB_with_temptarget=block.get("enableSMB_with_temptarget"),
        allowSMB_with_high_temptarget=block.get("allowSMB_with_high_temptarget"),
        enableSMB_always=block.get("enableSMB_always"),
        enableSMB_after_carbs=block.get("enableSMB_after_carbs"),
        maxSMBBasalMinutes=block.get("maxSMBBasalMinutes"),
        maxUAMSMBBasalMinutes=block.get("maxUAMSMBBasalMinutes"),
        bolus_increment=block.get("bolus_increment"),
        temptargetSet=block.get("temptargetSet"),
        autosens_max=block.get("autosens_max"),
        out_units=block.get("out_units"),
        lgsThreshold=block.get("lgsThreshold"),
        bgAccel_ISF_weight=block.get("bgAccel_ISF_weight"),
        bgBrake_ISF_weight=block.get("bgBrake_ISF_weight"),
        pp_ISF_weight=block.get("pp_ISF_weight"),
        lower_ISFrange_weight=block.get("lower_ISFrange_weight"),
        higher_ISFrange_weight=block.get("higher_ISFrange_weight"),
        dura_ISF_weight=block.get("dura_ISF_weight"),
        skip_neutral_temps=block.get("skip_neutral_temps"),
    )


def to_float(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        try:
            return float(x)
        except ValueError:
            return None
    return None


def build_iob_object(b):
    """Build a SimpleNamespace IOB object with numeric conversions."""
    if b is None:
        return None

    return SimpleNamespace(
        time=to_float(b.get("time") or b.get("timestamp")),
        iob=to_float(b.get("iob")),
        activity=to_float(b.get("activity")),
        bolussnooze=to_float(b.get("bolussnooze")),
        basaliob=to_float(b.get("basaliob")),
        netbasalinsulin=to_float(b.get("netbasalinsulin")),
        hightempinsulin=to_float(b.get("hightempinsulin")),
        lastBolusTime=to_float(b.get("lastBolusTime")),
        netInsulin=to_float(b.get("netInsulin")),
        extendedBolusInsulin=to_float(b.get("extendedBolusInsulin")),
        iobWithZeroTemp=(
            build_iob_object(b.get("iobWithZeroTemp"))
            if b.get("iobWithZeroTemp")
            else None
        ),
    )


def build_iob_array(iob_list):
    return [build_iob_object(b) for b in (iob_list or [])]


def debug_block(auto_block, row, blocks):
    print("\n" + "=" * 100)
    print(f"BLOCK {row.get('datetime')} (timestamp={row.get('timestamp')})")
    print("=" * 100)

    neighbors = find_neighbors(blocks, auto_block)

    print("\n--- RAW NEIGHBORS ---")
    print("GlucoseStatusAutoIsf:")
    print(json.dumps(neighbors["glucose"], ensure_ascii=False, indent=2))

    print("\nCurrentTemp:")
    print(json.dumps(neighbors["temp"], ensure_ascii=False, indent=2))

    print("\nIOB list (first element if any):")
    if neighbors["iob"]:
        print(json.dumps(neighbors["iob"][0], ensure_ascii=False, indent=2))
    else:
        print("no IOB")

    print("\nOapsProfileAutoIsf:")
    print(json.dumps(neighbors["profile"], ensure_ascii=False, indent=2))

    print("\nAutosensResult:")
    print(json.dumps(neighbors["autosens"], ensure_ascii=False, indent=2))

    print("\nMealData:")
    print(json.dumps(neighbors["meal"], ensure_ascii=False, indent=2))

    print("\nRT:")
    print(json.dumps(neighbors["rt"], ensure_ascii=False, indent=2))


def analyze_eventual_bg_for_timestamp(timestamp: int):
    blocks = load_blocks()
    auto_block = extract_autoisf_block(blocks, timestamp)
    if auto_block is None:
        logger.error("No AutoISF block found near timestamp")
        return None

    neighbors = find_neighbors(blocks, auto_block)

    if neighbors["profile"] is None:
        logger.error("No profile near AutoISF block")
        return None
    if not neighbors["iob"]:
        logger.error("No IOB near AutoISF block")
        return None

    # Build inputs list for build_inputs_from_block
    block_objs = [neighbors["glucose"]]
    if neighbors["temp"]:
        block_objs.append(neighbors["temp"])
    block_objs.extend(neighbors["iob"])
    if neighbors["profile"]:
        block_objs.append(neighbors["profile"])
    if neighbors["autosens"]:
        block_objs.append(neighbors["autosens"])
    if neighbors["meal"]:
        block_objs.append(neighbors["meal"])
    if neighbors["rt"]:
        block_objs.append(neighbors["rt"])

    inputs = build_inputs_from_block(block_objs)

    variable_sens, pred, dosing = run_autoisf_pipeline(inputs)

    return {
        "variable_sens": variable_sens,
        "eventual_bg": getattr(pred, "eventual_bg", None),
        "dosing": dosing,
        "inputs": inputs,
    }


def main():
    df = load_csv()
    blocks = load_blocks()

    df = df[df["aaps_eventual_bg"].notna()]
    bad = df[df["diff_eventual_bg"] < THRESHOLD]

    print(f"Всего строк с diff_eventual_bg < {THRESHOLD}: {len(bad)}")

    analyzed = 0

    for _, row in bad.iterrows():
        auto_block = extract_autoisf_block(blocks, row["timestamp"])
        if auto_block is None:
            continue
        debug_block(auto_block, row, blocks)
        analyzed += 1

    print("\nИТОГИ:")
    print(f"Реально проанализировано: {analyzed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Debug eventualBG differences for AutoISF blocks"
    )
    parser.add_argument(
        "--timestamp",
        type=int,
        help="Timestamp (ms) to locate AutoISF block",
        required=False,
    )
    args = parser.parse_args()

    if args.timestamp:
        res = analyze_eventual_bg_for_timestamp(args.timestamp)
        if res is None:
            print("No result")
        else:
            print("Variable sens:", res["variable_sens"])
            print("Eventual BG:", res["eventual_bg"])
            print("Dosing:", res["dosing"])
    else:
        main()
