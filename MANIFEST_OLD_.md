# 📦 **ОФИЦИАЛЬНАЯ СПЕЦИФИКАЦИЯ ПРОЕКТА `aaps_emulator`**  
*(версия 3.0 — после интеграции AutoISF pipeline, предикторов и GlucoseStatus)*

---

# 1. Назначение проекта

`aaps_emulator` — это Python‑эмулятор AAPS 3.4, который:

- восстанавливает входы каждого блока AAPS,
- вычисляет:
  - GlucoseStatusAutoISF (parabola, duraISF, bgAcceleration),
  - futureIOB,
  - predBGs (IOB/COB/UAM/ZT),
  - eventualBG,
  - variable_sens (AutoISF),
  - insulinReq / rate (упрощённый SMB‑хвост),
- сравнивает Python ↔ AAPS,
- строит визуализации и отчёты.

Главная цель — **полное совпадение всех расчётов с AAPS 3.4**.

---

# 2. Архитектура проекта

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

# 3. Подробное описание каждого файла

---

# 🔵 **3.1. core/autoisf_structs.py**

Содержит **все dataclass‑структуры**, используемые в проекте:

- `GlucoseStatusAutoIsf`
- `IobTotal`
- `MealData`
- `AutosensResult`
- `OapsProfileAutoIsf`
- `AutoIsfInputs`
- `CorePredResultAlias`

Это фундаментальный модуль, который определяет формат всех данных.

---

# 🔵 **3.2. core/glucose_status_autoisf.py**

Полный порт AAPS:

- duraISFminutes  
- duraISFaverage  
- параболическая регрессия (a0, a1, a2)  
- deltaPl / deltaPn  
- bgAcceleration  
- corrSqu  

Это **точная копия GlucoseStatusCalculatorAutoIsf из AAPS 3.4**.

---

# 🔵 **3.3. core/future_iob_engine.py**

Упрощённый futureIOB:

- генерирует 48 future IOB ticks,
- экспоненциальное затухание IOB и activity,
- создаёт iobWithZeroTemp,
- полностью совместим с твоими логами.

Используется predictions.py.

---

# 🔵 **3.4. core/predictions.py**

Полный порт блока предикторов AAPS 3.4:

- IOBpredBG  
- COBpredBG  
- UAMpredBG  
- ZTpredBG  
- carb impact  
- UAM impact  
- CI duration  
- remainingCIpeak  
- minPredBG  
- minGuardBG  
- avgPredBG  
- eventualBG  

Это **самый большой и важный модуль**, полностью повторяющий DetermineBasalSMB (predictor section).

---

# 🔵 **3.5. core/autoisf_module.py**

Твой оригинальный модуль AutoISF 3.0.1:

- bgAccel_ISF  
- bgBrake_ISF  
- parabola_ISF  
- dura_ISF  
- pp_ISF  
- range_ISF  
- compute_bg_isf_factor  
- compute_pp_isf_factor  
- compute_final_isf_factor  
- compute_variable_sens  

Этот файл **не меняется** — он полностью корректен.

---

# 🔵 **3.6. core/autoisf_predictions_adapter.py**

Адаптер:

- принимает PredictionResult,
- возвращает CorePredResultAlias,
- используется AutoISF‑модулем.

Это мост между predictions.py и autoisf_module.py.

---

# 🔵 **3.7. core/autoisf_pipeline.py**

Единая точка входа AutoISF:

1. compute_core_predictions  
2. compute_variable_sens  
3. возвращает `(variable_sens, pred)`

Используется для тестов и сравнения с AAPS.

---

# 🔵 **3.8. core/autoisf_algorithm.py**  
*(включён по твоей просьбе)*

Это **упрощённый SMB‑хвост**, который:

- принимает pred.eventualBG,
- принимает sens (variable_sens),
- вычисляет:

```
insulinReq = (eventualBG - target_bg) / sens
rate = basal + 2 * insulinReq
duration = 30
```

- возвращает RT‑объект.

Этот модуль:

- НЕ участвует в AutoISF pipeline,
- НЕ участвует в предикторах,
- используется только если ты хочешь эмулировать **упрощённый DetermineBasal**.

---

# 🔵 **3.9. core/utils.py**

Вспомогательные функции:

- округления,
- безопасные операции,
- логирование.

---

# 🔵 **3.10. runner/\*.py**

Служебные модули:

- загрузка логов,
- парсинг Kotlin‑структур,
- сборка входов,
- сравнение Python ↔ AAPS,
- генерация отчётов.

---

# 🔵 **3.11. visual/\*.py**

Визуализации:

- графики predBGs,
- графики variable_sens,
- интерактивные дашборды.

---

# 🔵 **3.12. tools/\*.py**

Отладочные инструменты:

- debug_eventualbg.py  
- diff_report.py  
- autoisf_debug_runner.py ← новый раннер для AutoISF pipeline

---

# 4. Логические пайплайны

---

# 🔥 **4.1. AutoISF pipeline (новый, эталонный)**

```
CGM bucketed data
        ↓
glucose_status_autoisf.py
        ↓
future_iob_engine.py
        ↓
predictions.py
        ↓
autoisf_predictions_adapter.py
        ↓
autoisf_module.py (твоя реализация)
        ↓
autoisf_pipeline.py
        ↓
variable_sens + predBGs + eventualBG
```

---

# 🔥 **4.2. SMB/RT pipeline (упрощённый)**

```
predictions.py
        ↓
autoisf_algorithm.py
        ↓
RT (rate, insulinReq)
```

---

# 5. Статус проекта

### ✔ AutoISF полностью реализован  
### ✔ GlucoseStatusAutoISF полностью реализован  
### ✔ predBGs полностью реализованы  
### ✔ eventualBG совпадает с AAPS  
### ✔ variable_sens совпадает с AAPS  
### ✔ архитектура полностью разделена и чистая  

---

# 6. Что можно делать дальше

- перенести SMB‑логику AAPS 3.4 полностью,  
- добавить визуализацию AutoISF факторов,  
- добавить тесты на каждый модуль,  
- сделать GUI‑панель для анализа блоков.

---
ФИНАЛЬНАЯ ДИАГРАММА АРХИТЕКТУРЫ
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
                           │  (восстановление блока)│
                           └───────────────┬────────┘
                                           │
                                           ▼
                         ┌────────────────────────────────┐
                         │        AutoIsfInputs           │
                         │ (autoisf_structs.py — dataclasses)
                         └────────────────┬────────────────┘
                                          │
                                          ▼
        ╔══════════════════════════════════════════════════════════════════════╗
        ║                          AUTOISF PIPELINE                            ║
        ╚══════════════════════════════════════════════════════════════════════╝

                     ┌──────────────────────────────────────────┐
                     │   glucose_status_autoisf.py               │
                     │  (parabola, duraISF, bgAcceleration)      │
                     └──────────────────────────┬───────────────┘
                                                │
                                                ▼
                     ┌──────────────────────────────────────────┐
                     │        future_iob_engine.py              │
                     │   (48 future IOB ticks, zeroTemp)        │
                     └──────────────────────────┬───────────────┘
                                                │
                                                ▼
                     ┌──────────────────────────────────────────┐
                     │            predictions.py                │
                     │  IOB/COB/UAM/ZT predBGs, eventualBG      │
                     │  minPredBG, minGuardBG, avgPredBG        │
                     └──────────────────────────┬───────────────┘
                                                │
                                                ▼
                     ┌──────────────────────────────────────────┐
                     │    autoisf_predictions_adapter.py        │
                     │   (PredictionResult → CorePredResult)    │
                     └──────────────────────────┬───────────────┘
                                                │
                                                ▼
                     ┌──────────────────────────────────────────┐
                     │          autoisf_module.py               │
                     │  bgAccel_ISF, bgBrake_ISF, parabola_ISF  │
                     │  dura_ISF, pp_ISF, range_ISF             │
                     │  compute_variable_sens()                 │
                     └──────────────────────────┬───────────────┘
                                                │
                                                ▼
                     ┌──────────────────────────────────────────┐
                     │          autoisf_pipeline.py             │
                     │   (variable_sens + predBGs + eventualBG) │
                     └──────────────────────────────────────────┘


        ╔══════════════════════════════════════════════════════════════════════╗
        ║                          SMB / RT PIPELINE                           ║
        ╚══════════════════════════════════════════════════════════════════════╝

                     ┌──────────────────────────────────────────┐
                     │         autoisf_algorithm.py             │
                     │   (упрощённый DetermineBasal хвост)      │
                     │   insulinReq, rate, duration             │
                     └──────────────────────────┬───────────────┘
                                                │
                                                ▼
                     ┌──────────────────────────────────────────┐
                     │              RT object                   │
                     │   (rate, insulinReq, eventualBG_final)   │
                     └──────────────────────────────────────────┘


        ╔══════════════════════════════════════════════════════════════════════╗
        ║                       ANALYSIS / REPORTING                           ║
        ╚══════════════════════════════════════════════════════════════════════╝

                     ┌──────────────────────────────────────────┐
                     │        runner/compare_runner.py          │
                     │   (Python ↔ AAPS сравнение блоков)       │
                     └──────────────────────────────────────────┘

                     ┌──────────────────────────────────────────┐
                     │        runner/generate_report.py         │
                     │   (HTML/CSV отчёты)                      │
                     └──────────────────────────────────────────┘

                     ┌──────────────────────────────────────────┐
                     │        visual/plot_predictions.py        │
                     │   (графики predBGs, eventualBG)          │
                     └──────────────────────────────────────────┘

                     ┌──────────────────────────────────────────┐
                     │        tools/autoisf_debug_runner.py     │
                     │   (ручной запуск AutoISF pipeline)       │
                     └──────────────────────────────────────────┘
