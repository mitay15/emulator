# 📄 **MANIFEST.md — Полное описание проекта AAPS Emulator**

## 📌 Назначение проекта

AAPS Emulator — это полностью воспроизводимая Python‑реализация алгоритма **AUTOISF** и связанных модулей AndroidAPS 3.4, включая:

- парсинг Kotlin‑логов AAPS  
- восстановление входных данных алгоритма  
- выполнение AutoISF → Predictions → DetermineBasal  
- сравнение результатов Python ↔ AAPS  
- генерацию отчётов и визуализаций  

Проект предназначен для анализа, тестирования и исследования алгоритма AUTOISF вне AndroidAPS.

---

# 📁 **1. Корневая структура проекта**

aaps_emulator/                     ← корень проекта (репозиторий и пакет)
│
├── __init__.py                    ← пакет Python
├── run.py                         ← CLI
│
├── core/                          ← алгоритм AUTOISF
│   ├── autoisf_pipeline.py
│   ├── autoisf_structs.py
│   ├── determine_basal.py
│   ├── future_iob_engine.py
│   ├── glucose_status_autoisf.py
│   ├── predictions.py
│   ├── utils.py
│   └── ...
│
├── runner/                        ← парсинг логов, сравнение
│   ├── compare_runner.py
│   ├── load_logs.py
│   ├── build_inputs.py
│   ├── kotlin_parser.py
│   ├── generate_report.py
│   └── ...
│
├── visual/                        ← визуализация
│   ├── dashboard.py
│   ├── plot_predbgs.py
│   └── ...
│
├── tools/                         ← утилиты
│   ├── show_inputs.py
│   ├── filter_clean_blocks.py
│   ├── generate_inputs_from_logs.py
│   ├── generate_inputs_cache.py
│   └── ...
│
├── data/                          ← данные
│   ├── cache/
│   ├── logs/
│   └── reports/
│
├── tests/                         ← тесты
│   ├── test_single_block_from_log.py
│   ├── test_all_blocks_parametrized.py
│   ├── test_full_pipeline.py
│   ├── test_full_suite.py
│   ├── test_plot_predbgs.py
│   ├── test_heatmap.py
│   ├── test_kotlin_parser.py
│   ├── conftest.py
│   └── ...
│
├── README.md
├── setup.py
├── setup.cfg
├── py

---

# 📁 **2. Пакет aaps_emulator/**

Главный Python‑пакет.

### 📄 `__init__.py`
Обозначает пакет.

### 📄 `run.py`
CLI‑интерфейс:

- принимает аргументы `--log`, `--html`, `--csv`, `--fast`, `--dump-parsed`
- вызывает compare_runner
- строит HTML‑дашборд
- сохраняет CSV‑отчёты

---

# 📁 **3. core/** — Алгоритм AUTOISF

Основная логика алгоритма.

### 📄 `autoisf_pipeline.py`
Главный pipeline:

- собирает inputs
- вызывает AutoISF
- вызывает Predictions
- вызывает DetermineBasal
- возвращает полный результат блока

### 📄 `autoisf_module.py`
Реализация AutoISF:

- autosens
- meal adjustments
- UAM adjustments
- sensitivity scaling
- variable_sens

### 📄 `autoisf_structs.py`
Структуры данных:

- Profile
- Autosens
- Meal
- IOB
- Inputs
- GlucoseStatus

### 📄 `glucose_status_autoisf.py`
Анализ истории BG:

- delta
- short_avg
- long_avg
- noise filtering

### 📄 `future_iob_engine.py`
Генерация будущего IOB.

### 📄 `predictions.py`
Полный движок предсказаний:

- eventualBG
- minPredBG
- minGuardBG
- predBGs (IOB/COB/UAM/ZT)

### 📄 `determine_basal.py`
Реализация DetermineBasal:

- insulinReq
- rate
- duration
- SMB
- safety caps
- LGS threshold

### 📄 `utils.py`
Вспомогательные функции:

- round_half_even
- безопасный парсер чисел
- форматирование

---

# 📁 **4. runner/** — Парсинг логов и сравнение

### 📄 `compare_runner.py`
Главный модуль сравнения Python ↔ AAPS:

- загружает логи
- собирает блоки
- строит inputs
- запускает pipeline
- сравнивает результаты
- сохраняет mismatch‑блоки
- генерирует summary.csv / summary.json

### 📄 `load_logs.py`
Загрузка логов:

- JSON
- ZIP
- LOG

### 📄 `kotlin_parser.py`
Разбор Kotlin‑структур:

- превращает Kotlin‑объекты в Python‑dict

### 📄 `build_inputs.py`
Восстановление входных данных:

- glucose_status
- autosens
- profile
- meal
- iob_data_array

### 📄 `generate_report.py`
Генерация CSV‑отчётов.

### 📄 `generate_inputs_from_logs.py`
Создание `inputs_before_algo_block_*.json`.

### 📄 `generate_inputs_cache.py`
Кеширование inputs.

---

# 📁 **5. visual/** — Визуализация

### 📄 `dashboard.py`
HTML‑дашборд Plotly:

- графики BG
- predBGs
- ошибки
- сравнение Python ↔ AAPS

### 📄 `plot_predbgs.py`
Графики предсказаний BG.

### 📄 `heatmap.py`
Тепловые карты ошибок.

---

# 📁 **6. tools/** — Утилиты

### 📄 `show_inputs.py`
Показ входных данных по номеру блока.

### 📄 `filter_clean_blocks.py`
Фильтрация clean‑блоков.

### 📄 `generate_inputs_from_logs.py`
Генерация inputs из логов.

### 📄 `generate_inputs_cache.py`
Создание кеша inputs.

---

# 📁 **7. tests/** — Тесты

### 📄 `test_full_pipeline.py`
Smoke‑тест pipeline.

### 📄 `test_all_blocks_parametrized.py`
Проверка всех блоков из cache.

### 📄 `test_single_block_from_log.py`
Тест одного блока.

### 📄 `test_kotlin_parser.py`
Тест парсера Kotlin.

### 📄 `test_plot_predbgs.py`
Тест графиков.

### 📄 `test_heatmap.py`
Тест heatmap.

### 📄 `test_full_suite.py`
Полный интеграционный тест.

### 📄 `conftest.py`
Фикстуры.

---

# 📁 **8. data/** — Данные

### 📁 `logs/`
Исходные AAPS‑логи.

### 📁 `cache/`
inputs_before_algo_block_*.json.

### 📁 `clean/`
clean‑блоки.

### 📁 `reports/`
CSV/HTML отчёты.

### 📄 `mismatch_block_*.json`
Mismatch‑диагностика.

---

# 📁 **9. reports/**

Автоматически генерируемые:

- summary.csv  
- summary.json  

---

# 📁 **10. Конфигурационные файлы**

### 📄 `setup.py`
Установка пакета.

### 📄 `setup.cfg`
Настройки ruff, pytest, mypy.

### 📄 `pyproject.toml`
Мета‑конфигурация.

### 📄 `requirements.txt`
Зависимости.

### 📄 `pytest.ini`
Настройки pytest.

### 📄 `.gitignore`
Исключения.

### 📄 `.pre-commit-config.yaml`
Хуки ruff + mypy.

---

# 📁 **11. Служебные файлы**

### 📄 `run_tests.py`
Удобный запуск тестов.

### 📄 `README.md`
Документация.

---

# 📁 **12. Оригинальные файлы AAPS 3.4 (референс)**

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

