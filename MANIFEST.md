# 📄 **MANIFEST.md — Полное описание проекта AAPS Emulator (АКТУАЛЬНО)**

## 📌 Назначение проекта

**AAPS Emulator** — это полноценный Python‑пакет, реализующий алгоритм **AUTOISF** и связанные компоненты AndroidAPS 3.4:

- парсинг Kotlin‑логов AAPS  
- восстановление входных данных алгоритма  
- выполнение AutoISF → Predictions → DetermineBasal  
- сравнение Python ↔ AAPS  
- генерация отчётов и визуализаций  
- интерактивный HTML‑отчёт  

Проект предназначен для анализа, тестирования и исследования алгоритма AUTOISF вне AndroidAPS.

---

# 📁 **1. Корневая структура проекта (ПАКЕТ)**

```
AAPS-Emulator/
│
├── pyproject.toml
├── README.md
├── run_all.py
├── run_tests.py
│
└── aaps_emulator/                 ← Python‑пакет
    │
    ├── __init__.py
    │
    ├── core/
    │   ├── __init__.py
    │   ├── autoisf_pipeline.py
    │   ├── autoisf_structs.py
    │   ├── determine_basal.py
    │   ├── future_iob_engine.py
    │   ├── glucose_status_autoisf.py
    │   ├── predictions.py
    │   ├── utils.py
    │
    ├── runner/
    │   ├── __init__.py
    │   ├── compare_runner.py
    │   ├── load_logs.py
    │   ├── build_inputs.py
    │   ├── kotlin_parser.py
    │
    ├── tools/
    │   ├── __init__.py
    │   ├── run_full_report.py
    │   ├── plot_predbg_diff.py
    │   ├── heatmap_diff.py
    │   ├── generate_inputs_from_logs.py
    │   ├── debug_one_block.py
    │   ├── diff_report.py
    │   ├── generate_html_report_interactive.py
    │   ├── show_inputs.py
    │
    ├── tests/
    │   ├── __init__.py
    │   ├── conftest.py
    │   ├── test_single_block_from_log.py
    │   ├── test_all_blocks_parametrized.py
    │   ├── test_full_pipeline.py
    │   ├── test_full_suite.py
    │   ├── test_plot_predbgs.py
    │   ├── test_heatmap.py
    │   ├── test_kotlin_parser.py
    │
    └── data/
        ├── cache/
        ├── logs/
        └── reports/
```

---

# ❌ **2. Файлы, которые были удалены (и НЕ должны быть в MANIFEST.md)**

Эти файлы были удалены как устаревшие, дублирующие или сломанные:

```
aaps_emulator/runner/generate_report.py
aaps_emulator/tools/check_report.py
aaps_emulator/tools/inspect_cache.py
aaps_emulator/tools/filter_clean_blocks.py
aaps_emulator/tools/debug_eventualbg.py
aaps_emulator/tools/generate_html_report.py
run.py
```

---

# 📁 **3. core/** — Алгоритм AUTOISF

### ✔ autoisf_pipeline.py  
Главный pipeline: AutoISF → Predictions → DetermineBasal.

### ✔ autoisf_structs.py  
Структуры данных: Profile, Autosens, Meal, IOB, Inputs, GlucoseStatus.

### ✔ glucose_status_autoisf.py  
Анализ истории BG: delta, short_avg, long_avg, фильтрация.

### ✔ predictions.py  
Предсказания BG: eventualBG, minPredBG, minGuardBG, predBGs.

### ✔ determine_basal.py  
DetermineBasal: insulinReq, rate, duration, SMB, safety caps.

### ✔ future_iob_engine.py  
Генерация будущего IOB.

### ✔ utils.py  
Вспомогательные функции.

---

# 📁 **4. runner/** — Парсинг логов и сравнение

### ✔ compare_runner.py  
Главный модуль сравнения Python ↔ AAPS.

### ✔ load_logs.py  
Загрузка логов (JSON, ZIP, LOG).

### ✔ kotlin_parser.py  
Парсинг Kotlin‑структур.

### ✔ build_inputs.py  
Восстановление входных данных из логов.

---

# 📁 **5. tools/** — Утилиты и отчёты

### ✔ run_full_report.py  
Полный отчёт: compare_runner → heatmap → predBG diff → интерактивный HTML.

### ✔ plot_predbg_diff.py  
Универсальный график AAPS vs Python.

### ✔ heatmap_diff.py  
Тепловая карта ошибок.

### ✔ generate_inputs_from_logs.py  
Создание inputs_before_algo_block_*.json.

### ✔ debug_one_block.py  
Глубокая диагностика mismatch‑блока.

### ✔ diff_report.py  
Статистика по CSV.

### ✔ generate_html_report_interactive.py  
Интерактивный Plotly‑отчёт.

### ✔ show_inputs.py  
Просмотр входов по номеру блока.

---

# 📁 **6. tests/** — Тесты

Все тесты актуальны и соответствуют пакетной структуре:

- test_single_block_from_log.py  
- test_all_blocks_parametrized.py  
- test_full_pipeline.py  
- test_full_suite.py  
- test_plot_predbgs.py  
- test_heatmap.py  
- test_kotlin_parser.py  
- conftest.py  

---

# 📁 **7. data/** — Данные

### ✔ cache/  
inputs_before_algo_block_*.json  
mismatch_block_*.json  

### ✔ logs/  
исходные AAPS‑логи  

### ✔ reports/  
summary.json  
heatmaps  
predbg_diff  
interactive HTML  

---

# 📁 **8. Конфигурация пакета**

### ✔ pyproject.toml  
Единственный корректный способ установки пакета.

### ✔ run_all.py  
Единая точка входа для полного пайплайна.

### ✔ run_tests.py  
Запуск тестов.

---

# 📁 **9. Оригинальные файлы AAPS 3.4 (референс)**

Ты просил, чтобы я их помнил — и я помню:

### AUTOISF
- AutoISF.kt  
- Autosens.kt  
- AutosensResult.kt  

### Predictions
- Predictions.kt  
- UAM.kt  
- COB.kt  
- IOB.kt  

### DetermineBasal
- DetermineBasalAdapterSMB.kt  
- DetermineBasalResult.kt  

### Inputs
- GlucoseStatus.kt  
- IobCobCalculatorPlugin.kt  
- Profile.kt  
- MealData.kt  

---
