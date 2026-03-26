# AAPS AutoISF Emulator

Python‑эмулятор AutoISF (AAPS 3.0.1) с полным пайплайном сравнения Kotlin ↔ Python.

## Структура

- `core/` — реализация алгоритмов (AutoISF, predictions, determine_basal, future_iob_engine).
- `runner/` — загрузка логов, сбор входов, сравнение с AAPS (`compare_runner`).
- `tools/` — отчёты, визуализация, диагностика.
- `tests/` — вспомогательные скрипты для ручной проверки.

## Быстрый старт

Полный пайплайн:

```bash
python run_all.py
