import json
import sys

from aaps_emulator.core.autoisf_algorithm import determine_basal_autoisf


def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_one_case.py <input_json_file>")
        return

    with open(sys.argv[1], encoding="utf-8") as f:
        inp = json.load(f)

    gs = inp["glucose_status"]
    currenttemp = inp.get("current_temp")
    iob_array = inp.get("iob_array")
    profile = inp["profile"]
    autosens = inp.get("autosens")
    meal = inp.get("meal")
    rt = inp.get("rt")

    res, trace = determine_basal_autoisf(
        glucose_status=gs,
        currenttemp=currenttemp,
        iob_data_array=iob_array,
        profile=profile,
        autosens_data=autosens,
        meal_data=meal,
        rt=rt,
        trace_mode=True,
    )

    print("\n=== RESULT ===")
    print(res)

    print("\n=== TRACE ===")
    for name, val in trace:
        print(f"{name}: {val}")


if __name__ == "__main__":
    main()
