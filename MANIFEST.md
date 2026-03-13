Димас, вот то, что ты просил: **полное, структурированное, профессиональное описание всего проекта**, как в хорошем техническом документе уровня production.  
Я собрал это так, чтобы ты мог использовать как архитектурный обзор, onboarding‑док, README или основу для wiki.

---

# 🧩 **AAPS Emulator — Полная архитектура проекта**

Ниже — полная структура проекта с описанием всех директорий и каждого файла: что он делает, зачем нужен, и как участвует в pipeline.

---

# 📁 **Корневая директория проекта**

| Файл / Папка | Назначение |
|--------------|------------|
| `core/` | Основная логика алгоритма AutoISF и OpenAPS‑подобных расчётов |
| `runner/` | Исполнение pipeline, сравнение с AAPS, загрузка логов |
| `tests/` | Интеграционные и модульные тесты |
| `tools/` | Утилиты для генерации входов, конвертации логов |
| `data/` | Логи, кеши, inputs_before_algo_block |
| `reports/` | CSV/JSON отчёты сравнения |
| `pyproject.toml` | Конфигурация ruff, mypy, зависимостей |
| `.pre-commit-config.yaml` | Хуки ruff + mypy |
| `.gitignore` | Исключения |
| `README.md` | Описание проекта |
| `venv/` | Локальное окружение (не в git) |

---

# 🧠 **Главная идея проекта**

Проект — это **полный Python‑эмулятор AutoISF и DetermineBasal из AAPS 3.4**, который:

1. Загружает реальные AAPS‑логи.
2. Восстанавливает входы алгоритма.
3. Запускает Python‑pipeline.
4. Сравнивает результаты с Kotlin‑оригиналом.
5. Генерирует отчёты и mismatch‑блоки.

---

# 📁 **core/** — *сердце алгоритма*

Это главный модуль, который реализует AutoISF, предсказания BG, чувствительность, eventualBG, minPredBG, minGuardBG, insulinReq, rate/duration и SMB.

---

## 🔹 `core/autoisf_pipeline.py`

**Главный pipeline**, который:

- принимает inputs (glucose_status, autosens, profile, meal, iob_data_array)
- вызывает AutoISF
- вызывает predictions
- вызывает determine_basal
- возвращает:
  - `variable_sens`
  - `pred` (eventualBG, minPredBG, minGuardBG, predBGs)
  - `dosing` (insulinReq, rate, duration, smb)

Это аналог `DetermineBasalAdapterSMB.kt` + `AutoISF.kt` + `Predictions.kt`.

---

## 🔹 `core/autoisf_module.py`

Полная реализация AutoISF:

- autosens‑факторы
- UAM‑факторы
- meal‑факторы
- sensitivity scaling
- variable_sens (как в AAPS 3.4)
- guard rails

Ты полностью реализовал AutoISF здесь, включая:

- autosens_ratio
- isf_adjustment
- uam_adjustment
- meal_adjustment
- final sensitivity

---

## 🔹 `core/predictions.py`

Реализует:

- eventualBG
- minPredBG
- minGuardBG
- predBGs (UAM/COB/IOB)
- логику AAPS 3.4 Predictions.kt

Мы исправляли:

- использование `RT.predBGs.UAM`, если есть
- корректный sens/base_sens
- guard rails
- уменьшение debug‑вывода

---

## 🔹 `core/determine_basal.py`

Полная реализация DetermineBasal:

- insulinReq
- rate
- duration
- SMB
- safety caps
- LGS threshold
- target BG fallback

Ты удалил 600+ строк legacy и переписал модуль полностью.

---

## 🔹 `core/utils.py`

Содержит:

- `round_half_even`
- безопасный парсер чисел
- вспомогательные функции

---

# 📁 **runner/** — *исполнение и сравнение*

---

## 🔹 `runner/compare_runner.py`

Главный инструмент сравнения Python ↔ AAPS:

- загружает логи
- собирает AutoISF‑блоки
- строит inputs
- запускает pipeline
- сравнивает результаты
- считает MAE/RMSE/max_diff
- сохраняет mismatch‑блоки
- генерирует summary CSV/JSON

Мы исправляли:

- типы idx
- timestamp
- timezone
- predBGs
- row["idx"]
- mypy‑совместимость

---

## 🔹 `runner/build_inputs.py`

Собирает inputs для pipeline:

- glucose_status
- current_temp
- iob_data_array
- profile
- autosens
- meal

Мы добавляли:

- передачу variable_sens
- корректную сериализацию

---

## 🔹 `runner/load_logs.py`

Загружает:

- JSON
- ZIP
- LOG

и превращает их в объекты AAPS.

---

## 🔹 `runner/generate_inputs_from_logs.py`

Создаёт `inputs_before_algo_block_*.json` из логов.

---

## 🔹 `runner/generate_inputs_cache.py`

Кеширует inputs для ускорения тестов.

---

# 📁 **tests/** — *интеграционные тесты*

Содержит:

- тесты pipeline
- тесты AutoISF
- тесты predictions
- тесты determine_basal
- интеграционные тесты, использующие `data/cache`

Ты чистил старые тесты и оставлял только совместимые.

---

# 📁 **tools/** — *вспомогательные утилиты*

- конвертеры логов
- генераторы inputs
- вспомогательные скрипты

---

# 📁 **data/**

- `logs/` — реальные AAPS‑логи
- `cache/` — inputs_before_algo_block
- `clean/` — clean‑блоки
- `mismatch_block_*.json` — mismatch‑диагностика

---

# 📁 **reports/**

- `summary.csv`
- `summary.json`

---

# 📁 **Оригинальные файлы AAPS 3.4 Kotlin, которые мы используем**

Ты просил, чтобы я их помнил — и я помню:

### 🔹 DetermineBasal / SMB
- `DetermineBasalAdapterSMB.kt`
- `DetermineBasalResult.kt`

### 🔹 AutoISF
- `AutoISF.kt`
- `Autosens.kt`
- `AutosensResult.kt`

### 🔹 Predictions
- `Predictions.kt`
- `UAM.kt`
- `COB.kt`
- `IOB.kt`

### 🔹 Inputs
- `GlucoseStatus.kt`
- `IobCobCalculatorPlugin.kt`
- `Profile.kt`
- `MealData.kt`

---

# 🎯 Хочешь — я могу:

- собрать это в красивый README.md
- сделать архитектурную диаграмму
- сделать PDF‑документ
- сделать wiki‑страницу
- сделать onboarding‑док для новых разработчиков

Скажи, в каком формате хочешь.