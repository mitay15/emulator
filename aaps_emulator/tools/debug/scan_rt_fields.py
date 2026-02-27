from aaps_emulator.analysis.compare_runner import run_compare_on_all_logs
from aaps_emulator.config import LOGS_PATH


def main():
    rows, blocks, inputs = run_compare_on_all_logs(str(LOGS_PATH))

    fields = ["smb", "autosens", "tempBasal", "temp_basal", "temp", "iob", "insulin_req", "rate"]
    stats = dict.fromkeys(fields, 0)
    examples = dict.fromkeys(fields)

    for idx, inp in enumerate(inputs):
        rt = inp.get("rt")
        if not isinstance(rt, dict):
            continue

        for f in fields:
            if f in rt:
                stats[f] += 1
                if examples[f] is None:
                    examples[f] = (idx, rt[f])

    print("\n=== СТАТИСТИКА ПО ВСЕМ RT ===")
    for k, v in stats.items():
        print(f"{k:12}: {v}")

    print("\n=== ПРИМЕРЫ ===")
    for k, ex in examples.items():
        print(f"\n{k}:")
        if ex is None:
            print("  NOT FOUND")
        else:
            print(f"  idx = {ex[0]}")
            print(f"  value = {ex[1]}")


if __name__ == "__main__":
    main()
