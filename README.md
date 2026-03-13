---

# 📘 **AAPS Emulator — Python AutoISF & DetermineBasal Emulator**

Полный Python‑эмулятор алгоритмов **AutoISF**, **Predictions**, **DetermineBasal**, совместимых с **AAPS 3.4 (AndroidAPS)**.  
Проект загружает реальные AAPS‑логи, восстанавливает входы алгоритма, запускает Python‑pipeline и сравнивает результаты с оригинальной Kotlin‑реализацией.

---

# 🚀 Возможности

- Полная реализация AutoISF (включая все факторы AAPS 3.4)
- Полная реализация DetermineBasal (SMB, insulinReq, rate/duration)
- Полная реализация Predictions (eventualBG, minPredBG, minGuardBG, predBGs)
- Полная совместимость с AAPS 3.4 Kotlin
- Загрузка JSON/ZIP/LOG логов AAPS
- Автоматическая генерация входов `inputs_before_algo_block`
- Сравнение Python ↔ AAPS с MAE/RMSE/max_diff
- Генерация mismatch‑блоков
- Генерация CSV/JSON отчётов
- Интеграционные тесты

---

# 📁 Структура проекта

```
aaps_emulator/
│
├── core/
├── runner/
├── tests/
├── tools/
├── data/
├── reports/
│
├── pyproject.toml
├── README.md
└── .pre-commit-config.yaml
```

---

# 🧩 **core/** — ядро алгоритма

| Файл | Назначение |
|------|------------|
| **autoisf_pipeline.py** | Главный pipeline: AutoISF → Predictions → DetermineBasal |
| **autoisf_module.py** | Полная реализация AutoISF (autosens, UAM, meal, sensitivity scaling) |
| **predictions.py** | eventualBG, minPredBG, minGuardBG, predBGs (UAM/COB/IOB) |
| **determine_basal.py** | insulinReq, rate, duration, SMB, safety caps |
| **utils.py** | round_half_even, безопасный парсер чисел, вспомогательные функции |

### 🔥 Особенности реализации

- Полное соответствие AAPS 3.4 Kotlin
- Исправлены guard rails
- Исправлены predBGs (UAM/COB/IOB)
- Исправлены eventualBG/minPredBG/minGuardBG
- Удалено 600+ строк legacy DetermineBasal
- Полная поддержка variable_sens

---

# 🏃 **runner/** — исполнение и сравнение

| Файл | Назначение |
|------|------------|
| **compare_runner.py** | Сравнение Python ↔ AAPS, генерация отчётов |
| **build_inputs.py** | Восстановление входов алгоритма из логов |
| **load_logs.py** | Загрузка JSON/ZIP/LOG логов AAPS |
| **generate_inputs_from_logs.py** | Генерация inputs_before_algo_block |
| **generate_inputs_cache.py** | Кеширование inputs |

### 🔥 Особенности

- Полная поддержка clean‑блоков
- Корректная обработка idx
- Корректная обработка timestamp/timezone
- Генерация mismatch‑блоков
- MAE/RMSE/max_diff для predBGs

---

# 🧪 **tests/** — тесты

| Тип тестов | Описание |
|------------|----------|
| Интеграционные | Сравнение Python ↔ AAPS по реальным логам |
| Unit‑тесты | AutoISF, Predictions, DetermineBasal |
| Cache‑тесты | Проверка inputs_before_algo_block |

---

# 🛠 **tools/** — утилиты

| Файл | Назначение |
|------|------------|
| **generate_inputs_from_logs.py** | Генерация inputs из логов |
| **generate_inputs_cache.py** | Создание кеша inputs |
| **конвертеры логов** | Преобразование форматов |

---

# 📂 **data/**

| Папка | Содержимое |
|--------|------------|
| `logs/` | Реальные AAPS‑логи |
| `cache/` | inputs_before_algo_block |
| `clean/` | clean‑блоки |
| `mismatch_block_*.json` | mismatch‑диагностика |

---

# 📊 **reports/**

| Файл | Назначение |
|------|------------|
| `summary.csv` | Сводка по всем блокам |
| `summary.json` | Полный отчёт |

---

# 🧬 Оригинальные файлы AAPS 3.4 Kotlin (используются для соответствия)

### DetermineBasal / SMB
- `DetermineBasalAdapterSMB.kt`
- `DetermineBasalResult.kt`

### AutoISF
- `AutoISF.kt`
- `Autosens.kt`
- `AutosensResult.kt`

### Predictions
- `Predictions.kt`
- `UAM.kt`
- `COB.kt`
- `IOB.kt`

### Inputs
- `GlucoseStatus.kt`
- `IobCobCalculatorPlugin.kt`
- `Profile.kt`
- `MealData.kt`

---

# 🔧 Установка

```
pip install -r requirements.txt
pre-commit install
```

---

# ▶️ Запуск сравнения

```
python -m runner.compare_runner --log path/to/log.json
```

---

# 📈 Генерация отчёта

```
python -m runner.compare_runner --report
```

---

# 🤝 Вклад в проект

Pull‑requests приветствуются.  
Проект использует:

- ruff (lint + fix)
- mypy (strict)
- pre‑commit hooks

---
