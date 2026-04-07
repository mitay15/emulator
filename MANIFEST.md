# ✅ **MANIFEST.md (полная профессиональная версия)**

```markdown
# AAPS‑Emulator — Manifest

## Обзор проекта

**AAPS‑Emulator** — это Python‑реализация алгоритма AutoISF и предсказаний AndroidAPS (версия 3.4), созданная для полного паритета с оригинальной логикой.  
Проект включает:

- полный AutoISF pipeline  
- DetermineBasal  
- Predictions (IOB/COB/UAM/ZT)  
- парсер Kotlin‑объектов  
- генерацию входов для алгоритма  
- сравнение Python ↔ AAPS  
- визуализацию  
- отчётность  
- **Auto‑GA v3** — профессиональный оптимизатор профиля  

Проект используется для:

- регрессионного тестирования  
- анализа поведения алгоритма  
- отладки  
- CI‑валидации  
- исследования AutoISF  
- автоматического подбора sens/carb_ratio/AutoISF параметров  

---

# 📁 Структура проекта

```
AAPS-Emulator/
├── aaps_emulator/
├── data/
├── out/
├── scripts/
├── tests/
├── .github/
├── MANIFEST.md
├── INSTALL.md
├── README.md
├── pyproject.toml
├── requirements.txt
├── run_all.py
├── run_tests.py
└── HOW_START_CHECK.md


aaps_emulator/
│   __init__.py
│   import_check_output.txt
│
├── core/                     ← ядро эмулятора AutoISF
│   ├── aps_what_if.py
│   ├── autoisf_full.py
│   ├── autoisf_pipeline.py
│   ├── autoisf_predictions_adapter.py
│   ├── autoisf_structs.py
│   ├── block_utils.py
│   ├── cache.py
│   ├── determine_basal.py
│   ├── future_iob_engine.py
│   ├── glucose_status_autoisf.py
│   ├── predictions.py
│   ├── utils.py
│   └── __init__.py
│
├── optimizer/                ← Auto‑GA v3 оптимизатор
│   ├── autoisf_internal.py
│   ├── crossover.py
│   ├── fitness_functions.py
│   ├── genetic_optimizer.py
│   ├── mutation.py
│   ├── population.py
│   ├── utils.py
│   └── __init__.py
│
├── gui/                      ← Streamlit GUI
│   ├── gui_simulator.py
│   └── __init__.py
│
└── runner/                   ← инструменты для запуска и сравнения
    ├── build_inputs.py
    ├── compare_runner.py
    ├── debug_load.py
    ├── kotlin_parser.py
    ├── load_logs.py
    └── __init__.py

```

---

# 🔬 **aaps_emulator/core** — ядро эмулятора AutoISF

Полная реализация алгоритма AndroidAPS 3.4.

## **aps_what_if.py**
Сценарный анализ: пересчёт AutoISF при изменённых входах (what‑if simulation).

## **autoisf_full.py**
Детальная реализация AutoISF:

- bgAccel / bgBrake адаптации  
- pp / dura адаптации  
- lower/higher ISF range  
- итоговый autoISF_factor  
- variable_sens  
- ограничения autoISF_min/max  

## **autoisf_pipeline.py**
Оркестратор AutoISF:

- сбор входов  
- вычисление variable_sens  
- вычисление dosing  
- генерация предсказаний  
- fallback‑логика  
- возврат структурированных результатов  

## **autoisf_predictions_adapter.py**
Адаптер между AutoISF и Predictions:

- объединяет результаты  
- нормализует поля  
- обеспечивает совместимость с AAPS  

## **autoisf_structs.py**
Типизированные структуры данных:

- GlucoseStatusAutoIsf  
- IobTotal  
- MealData  
- AutosensResult  
- ProfileAutoIsf  
- PredictionsResult  

Содержат дефолты, безопасные типы, raw‑данные.

## **block_utils.py**
Работа с логами:

- загрузка `.log`, `.json`, `.zip`  
- извлечение Kotlin‑объектов  
- группировка блоков по timestamp  
- нормализация структуры  

## **cache.py**
Кэширование:

- FITNESS_CACHE  
- кэширование pipeline результатов  

## **determine_basal.py**
Реализация DetermineBasal:

- SMB  
- temp basal  
- insulinReq  
- ограничения безопасности  

## **future_iob_engine.py**
Расчёт будущего IOB для предсказаний.

## **glucose_status_autoisf.py**
Обработка данных о глюкозе:

- delta  
- prevDelta  
- noise  
- безопасные преобразования  

## **predictions.py**
Генерация predBG:

- IOB  
- COB  
- UAM  
- ZT  
- eventualBG  
- minPredBG  
- minGuardBG  

## **utils.py**
Вспомогательные функции:

- безопасные конвертеры  
- округления  
- clamp  
- фильтры блоков  
- RMSE/MAE  

---

# 🤖 **aaps_emulator/optimizer** — Auto‑GA v3

Профессиональный оптимизатор профиля.

## **genetic_optimizer.py**
Auto‑GA v3:

- адаптивная мутация  
- адаптивный элитизм  
- адаптивный размер популяции  
- оценка разнообразия популяции  
- адаптивные диапазоны параметров  
- мягкий early stopping  
- интеграция с GUI  

## **fitness_functions.py**
Оценка качества профиля:

- MAE eventualBG  
- гипо/гипер штрафы  
- SMB штрафы  
- автоISF min/max штрафы  
- стабильность variable_sens  
- мягкие ограничения  
- кэширование fitness  

## **autoisf_internal.py**
Внутренние переменные AutoISF:

- bgAccel  
- bgBrake  
- pp  
- dura  
- weighted_sum  
- autoISF_factor  
- variable_sens  

## **population.py**
Генерация начальной популяции:

- диапазоны параметров  
- случайные значения  
- нормализация  

## **mutation.py**
Мутация:

- адаптивная интенсивность  
- clamp  
- учёт диапазонов  

## **crossover.py**
Кроссовер:

- uniform  
- mixed  
- one‑point  

## **utils.py**
Служебные функции:

- merge_profiles  
- diff_profiles  
- clamp  
- safe_float  

---

# 🖥 **aaps_emulator/gui**

## **gui_simulator.py**
Streamlit‑GUI:

- загрузка логов  
- выбор диапазона дат  
- редактирование профиля  
- запуск Auto‑GA v3  
- отображение fitness  
- визуализация истории поколений  
- вывод изменений профиля  
- сохранение результата  

---

# ⚙️ **aaps_emulator/runner**

## **build_inputs.py**
Преобразование блоков в AutoIsfInputs:

- безопасные конвертеры  
- обработка None  
- нормализация профиля  
- построение всех структур  

## **compare_runner.py**
Сравнение Python ↔ AAPS:

- прогон всех блоков  
- сравнение eventualBG, minPredBG, SMB, variable_sens  
- сохранение mismatch‑блоков  
- генерация отчётов  

## **debug_load.py**
Отладочная загрузка блоков.

## **kotlin_parser.py**
Парсер Kotlin‑объектов:

- поиск имени  
- балансировка скобок  
- извлечение ключ‑значение  
- конвертация типов  
- сохранение raw  

## **load_logs.py**
Загрузка логов:

- рекурсивный поиск  
- поддержка `.log`, `.json`, `.zip`  
- извлечение Kotlin‑объектов  

---

# 🧰 **scripts**

## **compare_real_vs_aaps.py**
Ad‑hoc сравнение Python ↔ AAPS.

## **quick_visual_test.py**
Быстрая визуализация predBG.

## **check_all.ps1**
Запуск полного набора проверок.

---

# 🧪 **tests**

Полный набор тестов:

- парсинг Kotlin  
- построение входов  
- AutoISF pipeline  
- DetermineBasal  
- Predictions  
- визуализация  
- heatmap  
- сравнение с эталонными блоками  

---

# 📁 **data/**

- **logs/** — исходные логи AAPS  
- **cache/** — inputs_before_algo_block, mismatch‑блоки  
- **clean/** — clean‑блоки  
- **reports/** — HTML, PNG, heatmaps  

---

# 🚀 Основные сценарии использования

### Быстрый прогон сравнения
```bash
python -m aaps_emulator.runner.compare_runner --fast
```

### Полный отчёт
```bash
python -m aaps_emulator.tools.run_full_report --open
```

### Запуск GUI
```bash
streamlit run aaps_emulator/gui/gui_simulator.py
```

### Запуск тестов
```bash
pytest -q
```

---

# 📌 Рекомендации по разработке

- использовать pre‑commit (ruff, autoflake)  
- проверять паритет на эталонных блоках  
- добавлять тесты при изменении парсера или AutoISF  
- хранить артефакты в `data/`, а не в пакете  

---
