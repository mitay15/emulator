from aaps_emulator.analysis.compare_runner import run_compare_on_all_logs

rows, blocks, inputs = run_compare_on_all_logs("logs")

print(f"Готово! Обработано {len(rows)} записей.")
