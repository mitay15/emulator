Димас, держи — **полный, аккуратный, современный README.md**, который полностью соответствует текущей архитектуре проекта, включает все файлы, роли, пайплайны, и может быть положен прямо в корень репозитория.

Я сделал его в стиле профессиональных open‑source проектов: структурированный, читаемый, с диаграммами, описанием модулей и пайплайнов.

---

# 📘 **README.md — AAPS Emulator (AutoISF + Predictions Engine)**
*(официальная версия 3.0)*

---

# 🚀 AAPS Emulator — Python‑эмулятор AutoISF и предикторов AAPS 3.4

`aaps_emulator` — это высокоточный Python‑движок, который полностью повторяет алгоритмы AAPS 3.4:

- **GlucoseStatusAutoISF** (parabola, duraISF, bgAcceleration)
- **futureIOB**
- **predBGs** (IOB/COB/UAM/ZT)
- **eventualBG**
- **variable_sens (AutoISF)**
- **упрощённый SMB/RT‑контроллер**

Проект читает реальные AAPS‑логи, восстанавливает входы каждого блока и сравнивает результаты Python ↔ AAPS.

Цель — **полное совпадение всех расчётов с AAPS 3.4**.

---

# 📂 Структура проекта

```
aaps_emulator/
│
├── core/
│   ├── autoisf_structs.py
│   ├── glucose_status_autoisf.py
│   ├── future_iob_engine.py
│   ├── predictions.py
│   ├── autoisf_predictions_adapter.py
│   ├── autoisf_pipeline.py
│   ├── autoisf_module.py
│   ├── autoisf_algorithm.py
│   └── utils.py
│
├── runner/
│   ├── load_logs.py
│   ├── build_inputs.py
│   ├── compare_runner.py
│   ├── generate_report.py
│   └── kotlin_parser.py
│
├── visual/
│   ├── dashboard.py
│   ├── plot_predictions.py
│
├── data/
│   ├── logs/
│   ├── reports/
│   └── cache/
│
└── tools/
    ├── debug_eventualbg.py
    ├── diff_report.py
    └── autoisf_debug_runner.py
```

---

# 🧠 Архитектура (диаграмма)

```
                         ┌──────────────────────────────┐
                         │        AAPS LOGS / CGM        │
                         └───────────────┬───────────────┘
                                         │
                                         ▼
                           ┌────────────────────────┐
                           │   runner/load_logs.py  │
                           └───────────────┬────────┘
                                           │
                                           ▼
                           ┌────────────────────────┐
                           │ runner/build_inputs.py │
                           └───────────────┬────────┘
                                           │
                                           ▼
                         ┌────────────────────────────────┐
                         │        AutoIsfInputs           │
                         └────────────────┬────────────────┘
                                          │
                                          ▼
        ╔══════════════════════════════════════════════════════════════════════╗
        ║                          AUTOISF PIPELINE                            ║
        ╚══════════════════════════════════════════════════════════════════════╝

                     ┌──────────────────────────────────────────┐
                     │   glucose_status_autoisf.py               │
                     └──────────────────────────┬───────────────┘
                                                │
                                                ▼
                     ┌──────────────────────────────────────────┐
                     │        future_iob_engine.py              │
                     └──────────────────────────┬───────────────┘
                                                │
                                                ▼
                     ┌──────────────────────────────────────────┐
                     │            predictions.py                │
                     └──────────────────────────┬───────────────┘
                                                │
                                                ▼
                     ┌──────────────────────────────────────────┐
                     │    autoisf_predictions_adapter.py        │
                     └──────────────────────────┬───────────────┘
                                                │
                                                ▼
                     ┌──────────────────────────────────────────┐
                     │          autoisf_module.py               │
                     └──────────────────────────┬───────────────┘
                                                │
                                                ▼
                     ┌──────────────────────────────────────────┐
                     │          autoisf_pipeline.py             │
                     └──────────────────────────────────────────┘


        ╔══════════════════════════════════════════════════════════════════════╗
        ║                          SMB / RT PIPELINE                           ║
        ╚══════════════════════════════════════════════════════════════════════╝

                     ┌──────────────────────────────────────────┐
                     │         autoisf_algorithm.py             │
                     └──────────────────────────┬───────────────┘
                                                │
                                                ▼
                     ┌──────────────────────────────────────────┐
                     │              RT object                   │
                     └──────────────────────────────────────────┘
```

---

# 📘 Описание модулей

---

## 🔵 core/autoisf_structs.py
Dataclasses для всех структур:

- GlucoseStatusAutoIsf
- IobTotal
- MealData
- AutosensResult
- OapsProfileAutoIsf
- AutoIsfInputs
- CorePredResultAlias

---

## 🔵 core/glucose_status_autoisf.py
Полный порт AAPS GlucoseStatusCalculatorAutoIsf:

- duraISFminutes
- duraISFaverage
- параболическая регрессия (a0, a1, a2)
- deltaPl / deltaPn
- bgAcceleration
- corrSqu

---

## 🔵 core/future_iob_engine.py
Генерация futureIOB:

- 48 future ticks
- экспоненциальное затухание
- iobWithZeroTemp

---

## 🔵 core/predictions.py
Полный порт предикторов AAPS:

- IOBpredBG
- COBpredBG
- UAMpredBG
- ZTpredBG
- carb impact
- UAM impact
- minPredBG
- minGuardBG
- avgPredBG
- eventualBG

---

## 🔵 core/autoisf_predictions_adapter.py
Преобразует PredictionResult → CorePredResultAlias.

---

## 🔵 core/autoisf_module.py
Полная реализация AutoISF 3.0.1:

- bgAccel_ISF
- bgBrake_ISF
- parabola_ISF
- dura_ISF
- pp_ISF
- range_ISF
- compute_variable_sens

---

## 🔵 core/autoisf_pipeline.py
Единая точка входа AutoISF:

```
variable_sens, pred = run_autoisf_pipeline(inputs)
```

---

## 🔵 core/autoisf_algorithm.py
Упрощённый SMB‑хвост:

- insulinReq
- rate
- duration
- eventualBG_final

---

## 🔵 core/utils.py
Вспомогательные функции.

---

# 🏃 runner/\*.py

- **load_logs.py** — загрузка логов AAPS
- **build_inputs.py** — восстановление AutoIsfInputs
- **compare_runner.py** — сравнение Python ↔ AAPS
- **generate_report.py** — отчёты
- **kotlin_parser.py** — парсинг Kotlin‑структур

---

# 📊 visual/\*.py

- **dashboard.py** — интерактивные панели
- **plot_predictions.py** — графики predBGs

---

# 🛠 tools/\*.py

- **debug_eventualbg.py** — отладка eventualBG
- **diff_report.py** — сравнение блоков
- **autoisf_debug_runner.py** — ручной запуск AutoISF pipeline

---

# 🧪 Тестирование

Для ручного теста:

```
python tools/autoisf_debug_runner.py path/to/block.json
```

---

# 🎯 Статус проекта

- AutoISF полностью реализован
- GlucoseStatusAutoISF полностью реализован
- predBGs полностью реализованы
- eventualBG совпадает с AAPS
- variable_sens совпадает с AAPS
- архитектура чистая, модульная, расширяемая

---

Если хочешь — могу:

- добавить **Mermaid‑диаграмму**,
- сделать **README на английском**,
- или собрать **официальную документацию в формате Wiki**.
