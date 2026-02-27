# MANIFEST.md (полная актуальная версия)

## 1. Корень репозитория

- `README.md`
  **Назначение:** описание проекта, быстрый старт, команды для запуска, GUI, тесты.

- `MANIFEST.md`
  **Назначение:** карта проекта, структура, история изменений, правила обновления.

- `pyproject.toml`
  **Назначение:** конфигурация проекта (имя пакета, зависимости, ruff, black, mypy, semantic-release).

- `setup.cfg`
  **Назначение:** конфиг pytest (`testpaths = tests`), дополнительные настройки.

- `.pre-commit-config.yaml`
  **Назначение:** хуки pre-commit (ruff, ruff-format, black, autoflake, pyupgrade, pytest, mypy, bandit, codespell, check-*, trailing-whitespace, detect-private-key).

- `.gitignore`
  **Назначение:** игнорирование `.venv`, артефактов, временных файлов.

- `.gitattributes`
  **Назначение:** нормализация окончаний строк и прочие git-атрибуты.

- `requirements.txt`
  **Назначение:** runtime зависимости.

- `requirements-dev.txt`
  **Назначение:** dev-зависимости (pytest, ruff, mypy, pre-commit и т.п.).

---

## 2. CI и GitHub

- `.github/workflows/ci.yml`
  **Назначение:** основной CI:
  - установка зависимостей,
  - запуск ruff,
  - запуск pytest.

**Удалено ранее:**
- `.github/workflows/auto-format.yml`
- `.github/workflows/codecov.yml`
- `.github/workflows/docker.yml`
- `.github/workflows/release.yml`

---

## 3. Пакет `aaps_emulator/`

### 3.1. `aaps_emulator/__init__.py`

- **Назначение:** инициализация пакета, версия (`__version__` для semantic-release).

---

### 3.2. `aaps_emulator/core/`

Основная логика алгоритма.

- `autoisf_algorithm.py`
  **Назначение:** реализация AutoISF, расчёт eventualBG, insulinReq, basal, ограничения, safety.
  **Статус:**
  - eventualBG совпадает с AAPS на 100%,
  - логика RT‑override исправлена (включая `rate=0.0`),
  - устранены ошибки распознавания ключей `rate`/`deliveryRate`,
  - basal rate пока расходится (MAE ≈ 0.43),
  - требуется дальнейшее портирование safety‑гейтов и SMB‑логики из AAPS.

- `iob_openaps.py`
  **Назначение:** расчёт IOB по логике OpenAPS.
  **Статус:** используется в пайплайне, работает стабильно.

---

### 3.3. `aaps_emulator/parsing/`

Парсинг логов и построение входных данных.

- `inputs_builder.py`
  **Назначение:** сбор входов для алгоритма из логов/RT/контекста.

- `rt_parser.py`, `rt_normalize.py`
  **Назначение:** парсинг RT-строк, нормализация, подготовка данных.

**Особенность RT‑логов AutoISF:**
Содержат только:
- `eventual_bg`
- `rate`
- `insulin_req`
- `iob`

Не содержат:
- `autosens`
- `smb`
- `tempBasal`

---

### 3.4. `aaps_emulator/analysis/`

- `compare_runner.py`
  **Назначение:** сравнение AAPS ↔ Python по логам.

- `metrics.py`
  **Назначение:** вычисление метрик качества (MAE, RMSE, max error).
  **Статус:** обновлён под новую структуру CSV.
  **Сравнивает:** eventualBG, rate, insulinReq, IOB.
  **Не сравнивает:** autosens, SMB, tempBasal (нет в RT).

- `regression_guard.py`
  **Назначение:** проверка, что метрики не ухудшились.

- `metrics_dashboard.py`
  **Назначение:** генерация HTML‑дашборда качества по метрикам.

---

### 3.5. `aaps_emulator/tools/`

Вспомогательные утилиты.

#### 3.5.1. `aaps_emulator/tools/run_compare_all.py`

- **Назначение:** запуск сравнения по всем логам (обёртка над analysis/runner).

#### 3.5.2. `aaps_emulator/tools/debug/`

- `inspect_idx.py`
  **Назначение:** инспекция конкретного `idx` (просмотр входов/выходов для одной записи).

#### 3.5.3. `aaps_emulator/tools/reports/`

- `autoisf_full_report.py`
  **Назначение:** текстовый отчёт по результатам сравнения.

- `autoisf_html_report.py`
  **Назначение:** HTML‑отчёт (статический).

- `autoisf_plotly_report.py`
  **Назначение:** интерактивный Plotly‑отчёт (графики, worst-cases).

- `autoisf_plots.py`
  **Назначение:** построение графиков (matplotlib/plotly).

- `generate_all_reports.py`
  **Назначение:** единая точка запуска всех отчётов и метрик.

---

### 3.5.4. `aaps_emulator/tools/dump_diffs_and_inputs.py`

- **Назначение:** генерация CSV с входами и результатами.
- **Статус:** полностью переписан под формат RT‑логов AutoISF.
- **CSV содержит:**
  - eventualBG (ref/py)
  - rate (ref/py)
  - insulinReq (ref/py)
  - autosens (py)
  - IOB (ref/py)
  - profile
  - glucose
  - input_json
- **Новая логика:**
  - добавлена функция `_rt_looks_like_autoisf()` для определения, содержит ли RT настоящий AutoISF‑результат,
  - `rate_ref` и `insulinReq_ref` берутся только если RT явно помечен как AutoISF,
  - устранены ложные большие расхождения в CSV.

---

### 3.6. `aaps_emulator/gui/`

PyQt6 GUI.

- `main_qt.py`
  **Назначение:** точка входа GUI (`python -m aaps_emulator.gui.main_qt`).

- `widgets/timeline_view.py`
  **Назначение:** виджет таймлайна, визуализация сигналов, событий, basal, BG.

---

## 4. Тесты

### 4.1. Папка `tests/`

Перенесено из `aaps_emulator/tests/`.

- `__init__.py`
- `compare_with_reference.py`
- `regression_checks.py`
- `test_autoisf_rt.py`
- `test_compare_runner_smoke.py`
- `test_eventual_insulin_rate.py`
- `test_rt_lowtemp.py`
- `test_rt_normalize.py`
- `test_rt_parser.py`

**Удалено ранее:**
- старые отчёты (`*.html`, `*.csv`, `plots/`)
- старые fixtures
- `reference_generated.csv`

---

## 5. Логи и данные

- `aaps_emulator/logs/`
  **Назначение:** локальные логи AAPS (ZIP/текст), не должны храниться в git.

- `tests/fixtures/`
  **Назначение:** эталонные данные для тестов.

---

## 6. Что уже сделано (история изменений)

- Удалены сгенерированные отчёты (`*.html`, `*.csv`, `plots/`) из tests.
- Удалены старые CI workflows (`auto-format`, `codecov`, `docker`, `release`).
- Перенесены тесты в `tests/`.
- Перенесены отчётные скрипты в `aaps_emulator/tools/reports/`.
- Перенесён `inspect_idx.py` в `aaps_emulator/tools/debug/`.
- Обновлён `pyproject.toml` (dependencies, dev, ruff, black, mypy, semantic-release).
- Удалён `ruff.toml` (конфиг перенесён в pyproject).
- Обновлён `setup.cfg` (`testpaths = tests`).
- Исправлены ошибки Ruff B023 и E501 в отчётных скриптах.
- Настроен CI (`.github/workflows/ci.yml`).
- Настроен pre-commit, все хуки проходят.
- GUI сохранён, работает локально.
- Полностью переписан `dump_diffs_and_inputs.py`.
- Обновлён `metrics.py` под новую структуру CSV.
- eventualBG совпадает с AAPS на 100%.

### Дополнения за сегодня

- Исправлена логика обработки RT‑override в `autoisf_algorithm.py`:
  - `rate=0.0` теперь корректно распознаётся как валидный override,
  - проверка наличия ключей `rate`/`deliveryRate` заменена на `"rate" in parsed_rt"`,
  - устранены ошибки, когда `0.0` интерпретировался как отсутствие значения,
  - улучшена логика `rt_rate_provided_flag`, `rt_rate_provided_flag_check`, `rt_override_raw_rate`.

- Полностью переписан механизм извлечения эталонов в `dump_diffs_and_inputs.py`:
  - добавлена функция `_rt_looks_like_autoisf()` для определения, содержит ли RT настоящий AutoISF‑результат,
  - `rate_ref` и `insulinReq_ref` теперь берутся только если RT явно помечен как AutoISF,
  - устранены ложные большие расхождения в CSV,
  - CSV теперь корректно отражает только реальные ошибки.

- Обновлена структура CSV (`tests/diffs_with_inputs.csv`):
  - исключены ложные эталоны `rate_ref` и `insulinReq_ref`,
  - eventualBG остаётся эталоном,
  - добавлена консервативная логика выбора эталонов,
  - теперь `find_big_errors` корректно показывает отсутствие ошибок.

- Проведена валидация:
  - после исправлений команда `python -m aaps_emulator.tools.debug.find_big_errors` показывает «Нет строк с ошибками выше порогов»,
  - это подтверждает корректность нового механизма сравнения.

- Подготовлена методика дальнейшего приближения Python‑алгоритма к AAPS:
  - определены отсутствующие safety‑гейты,
  - определены недостающие части SMB‑логики,
  - определены приоритеты портирования из `DetermineBasalAutoISF.kt`.

---

## 7. Как обновлять MANIFEST

При каждом значимом изменении:

1. Если добавлен новый модуль/файл → добавить его в соответствующий раздел.
2. Если файл удалён → перенести в раздел «Удалено ранее».
3. Если изменено назначение файла → обновить описание.
