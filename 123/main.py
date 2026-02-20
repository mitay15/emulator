from parser.file_loader import LogFileLoader
from parser.log_parser_json import AAPS34JSONParser

from stats.cycle_stats import CycleStats
from stats.export_csv import export_cycles_to_csv
from stats.plots import (
    plot_bg,
    plot_isf,
    plot_insulin_req,
    plot_predicted_bg,
    show_all,
)
from stats.compare import compare_suggested_vs_emulator

from emulator.determine_basal import DetermineBasalEngine
from emulator.cycle_model import CycleInput
from emulator.scenario import (
    run_scenario_change_isf,
    run_scenario_change_target,
    run_scenario_change_max_basal,
)


def process_logs(folder: str):
    loader = LogFileLoader(folder)
    parser = AAPS34JSONParser()

    stats = CycleStats()
    emulator = DetermineBasalEngine()

    current_glucose = None
    current_profile = None
    current_iob = None
    current_result = None
    current_suggested = None
    current_autoisf_factor = None

    print("\nНачинаю парсинг JSON логов AAPS 3.4...\n")

    for line in loader.iter_log_lines():
        # Глюкоза
        g = parser.parse_glucose(line)
        if g:
            current_glucose = g

        # Профиль
        p = parser.parse_profile(line)
        if p:
            current_profile = p

        # IOB
        iob = parser.parse_iob(line)
        if iob:
            current_iob = iob

        # APSResult → resultJson
        r = parser.parse_result(line)
        if r:
            current_result = r
            current_autoisf_factor = r.get("sensitivityRatio")

        # DeviceStatus → suggested
        s = parser.parse_suggested(line)
        if s:
            current_suggested = s

        # Когда есть glucose + profile + resultJson — считаем цикл
        if current_glucose and current_profile and current_result:
            bg = current_glucose.get("glucose")
            delta = current_glucose.get("delta")
            target = current_profile.get("target_bg")
            isf = current_profile.get("sens")
            insulinReq = current_result.get("insulinReq")
            rate = current_result.get("rate")
            duration = current_result.get("duration")
            reason = current_result.get("reason")

            print("\n=== NEW CYCLE (JSON) ===")
            print(f"BG: {bg} (Δ {delta})")
            print(f"Target: {target}")
            print(f"ISF: {isf}")
            print(f"AutoISF factor: {current_autoisf_factor}")
            print(f"InsulinReq (AAPS): {insulinReq}")
            print(f"Rate: {rate} U/h for {duration} min")
            print(f"Reason: {reason}")

            # Сохраняем цикл
            stats.cycles.append({
                "glucose": current_glucose,
                "profile": current_profile,
                "autoisf": current_autoisf_factor,
                "result": current_result,
                "suggested": {
                    "insulinReq": insulinReq,
                    "rate": rate,
                    "duration": duration,
                    "reason": reason,
                },
            })

            # Собираем CycleInput
            ci = CycleInput(
                glucose=current_glucose,
                profile=current_profile,
                autosens=None,
                autoisf=current_autoisf_factor,
                iob=current_iob,
                cob=None,
                predictions=current_result.get("predBGs"),
            )

            # Эмулятор (replay)
            emu = emulator.compute_from_input(ci)
            if emu:
                print("\n--- Эмулятор (replay) ---")
                print(f"Emu InsulinReq: {emu.insulinReq}")
                print(f"Emu Rate: {emu.rate}")
                print(f"Emu Reason: {emu.reason}")

            # WHAT-IF: ISF x0.8
            if isf:
                new_isf = isf * 0.8
                emu_isf = run_scenario_change_isf(ci, new_isf)
                if emu_isf:
                    print("\n--- WHAT IF: ISF x0.8 ---")
                    print(f"New ISF: {new_isf}")
                    print(f"InsulinReq: {emu_isf.insulinReq}")
                    print(f"Rate: {emu_isf.rate}")

            # WHAT-IF: Target = 90
            emu_target = run_scenario_change_target(ci, new_target=90)
            if emu_target:
                print("\n--- WHAT IF: Target = 90 ---")
                print(f"InsulinReq: {emu_target.insulinReq}")
                print(f"Rate: {emu_target.rate}")

            # WHAT-IF: maxBasal = 3.0
            emu_maxbasal = run_scenario_change_max_basal(ci, max_basal=3.0)
            if emu_maxbasal:
                print("\n--- WHAT IF: maxBasal = 3.0 ---")
                print(f"InsulinReq: {emu_maxbasal.insulinReq}")
                print(f"Rate: {emu_maxbasal.rate}")

            print("\n-----------------------------\n")

            # Сброс
            current_glucose = None
            current_profile = None
            current_iob = None
            current_result = None
            current_suggested = None
            current_autoisf_factor = None

    print("\n\n=== ИТОГОВАЯ СТАТИСТИКА ===\n")
    print(stats.summary())

    export_cycles_to_csv(stats.cycles, "cycles.csv")
    print("CSV сохранён в cycles.csv")

    diffs, avg = compare_suggested_vs_emulator(stats.cycles, emulator)
    if avg is not None:
        print(f"\nСреднее расхождение эмулятора по InsulinReq: {avg:.2f}%")

    plot_bg(stats.cycles)
    plot_isf(stats.cycles)
    plot_insulin_req(stats.cycles)
    plot_predicted_bg(stats.cycles)
    show_all()


if __name__ == "__main__":
    process_logs("data")
