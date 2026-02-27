Готово, Димас — ниже **полностью обновлённый MANIFEST.md**, уже приведённый в тот формат, который ты прислал, но **исправленный и синхронизированный с реальным состоянием твоего репозитория** после всех удалений, переносов и обновлений.

Ты можешь **просто скопировать и вставить** это в свой `MANIFEST.md`.

---

# MANIFEST.md (полная актуальная версия)

## 1. Корень репозитория

- `README.md`
  **Назначение:** описание проекта, быстрый старт, команды для запуска, GUI, тесты.

- `MANIFEST.md`
  **Назначение:** карта проекта, структура, история изменений, правила обновления.

- `pyproject.toml`
  **Назначение:** конфигурация проекта (имя пакета, зависимости, ruff, black, mypy, pytest, semantic-release).

- `setup.cfg`
  **Назначение:** конфигурация pytest (`testpaths = tests`), дополнительные настройки.

- `.pre-commit-config.yaml`
  **Назначение:** хуки pre-commit (ruff, ruff-format, black, autoflake, pyupgrade, pytest, mypy, bandit, codespell, check-*, trailing-whitespace, detect-private-key).

- `.gitignore`
  **Назначение:** игнорирование `.venv`, артефактов, временных файлов.

- `.gitattributes`
  **Назначение:** нормализация окончаний строк и прочие git-атрибуты.

- `requirements.txt`
  **Назначение:** runtime-зависимости.

- `requirements-dev.txt`
  **Назначение:** dev-зависимости (pytest, pytest-cov, ruff, mypy, pre-commit и т.п.).

---

## 2. CI и GitHub

- `.github/workflows/ci.yml`
  **Назначение:** основной CI:
  - установка зависимостей,
  - запуск ruff,
  - запуск mypy,
  - запуск pytest с покрытием,
  - загрузка HTML‑отчёта покрытия как artifact,
  - запуск сравнения Python ↔ AAPS.

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
  - исправлена логика RT‑override (`rate=0.0` теперь корректно),
  - исправлена проверка ключей `rate`/`deliveryRate`,
  - устранены ошибки `rt_rate_provided_flag`,
  - basal rate пока расходится (MAE ≈ 0.43),
  - требуется дальнейшее портирование safety‑гейтов и SMB‑логики из AAPS.

- `autoisf_types.py`
  **Назначение:** dataclasses для входов/выходов.

- `autoisf_trace.py`
  **Назначение:** трассировка вычислений.

- `iob_openaps.py`
  **Назначение:** расчёт IOB по логике OpenAPS.

---

### 3.3. `aaps_emulator/parsing/`
Парсинг логов и построение входных данных.

- `inputs_builder.py`
  **Назначение:** сбор входов для алгоритма.

- `rt_parser.py`
  **Назначение:** парсинг RT‑строк.

- `log_loader.py`
  **Назначение:** загрузка логов AAPS.

- `iob_events_builder.py`
  **Назначение:** построение IOB‑событий.

**Удалено ранее:**
- `rt_normalize.py` (файл отсутствует в проекте).

---

### 3.4. `aaps_emulator/analysis/`

- `compare_runner.py`
  **Назначение:** сравнение AAPS ↔ Python по логам.

- `metrics.py`
  **Назначение:** вычисление метрик качества (MAE, RMSE, max error).
  **Сравнивает:** eventualBG, rate, insulinReq, IOB.
  **Не сравнивает:** autosens, SMB, tempBasal (нет в RT).

- `metrics_dashboard.py`
  **Назначение:** HTML‑дашборд качества.

- `regression_guard.py`
  **Назначение:** проверка, что метрики не ухудшились.

---

### 3.5. `aaps_emulator/tools/`

#### 3.5.1. Основные утилиты

- `dump_diffs_and_inputs.py`
  **Назначение:** генерация CSV с входами и результатами.
  **Статус:** полностью переписан под формат RT‑логов AutoISF.

#### 3.5.2. Debug‑утилиты (`aaps_emulator/tools/debug/`)

- `debug_one_case.py`
  **Назначение:** пошаговая диагностика одного случая.

- `inspect_idx.py`
  **Назначение:** инспекция конкретного `idx`.

- `find_big_errors.py`
  **Назначение:** поиск крупных расхождений.

- `scan_rt_fields.py`
  **Назначение:** анализ RT‑полей.

#### 3.5.3. Отчёты (`aaps_emulator/tools/reports/`)

- `generate_all_reports.py`
  **Назначение:** генерация всех отчётов.

---

### 3.6. `aaps_emulator/gui/`

- `main_qt.py`
  **Назначение:** точка входа GUI.

---

## 4. Тесты

### 4.1. Папка `tests/`

```
tests/
  conftest.py
  test_autoisf_core_cases.py
  test_autoisf_extended_cases.py
  test_integration_logs.py
  test_regression_guard.py
  test_coverage_smoke.py
  data/
    logs/
```

### Описание тестов

- **test_autoisf_core_cases.py** — базовые unit‑тесты AutoISF.
- **test_autoisf_extended_cases.py** — расширенные unit‑тесты (SMB, UAM, COB, sensitivityRatio).
- **test_integration_logs.py** — сравнение Python ↔ AAPS по логам.
- **test_regression_guard.py** — проверка отсутствия падений на минимальных входах.
- **test_coverage_smoke.py** — проверка импорта ключевых модулей.
- **conftest.py** — фикстуры.

### Удалено ранее:

- test_compare_runner_smoke.py
- test_eventual_insulin_rate.py
- test_rt_lowtemp.py
- test_rt_normalize.py
- test_rt_parser.py
- старые отчёты (`*.html`, `*.csv`, `plots/`)
- reference_generated.csv

---

## 5. Логи и данные

- `tests/data/logs/`
  **Назначение:** реальные AAPS‑логи для интеграционных тестов.

- `reports/last_run/metrics.json`
  **Назначение:** результаты последнего анализа.

---

## 6. Что уже сделано (история изменений)

- Удалены старые CI workflows.
- Перенесены тесты в `tests/`.
- Перенесены отчётные скрипты в `aaps_emulator/tools/reports/`.
- Перенесён `inspect_idx.py` в debug/.
- Обновлён `pyproject.toml`.
- Удалён `ruff.toml`.
- Обновлён `setup.cfg`.
- Настроен CI.
- Настроен pre-commit.
- Полностью переписан `dump_diffs_and_inputs.py`.
- Обновлён `metrics.py`.
- eventualBG совпадает с AAPS на 100%.

### Дополнения за сегодня

- Исправлена логика RT‑override.
- Исправлена логика `rt_rate_provided_flag`.
- Исправлена обработка `rate=0.0`.
- Исправлена логика выбора эталонов в CSV.
- Устранены ложные большие расхождения.
- Обновлён regression_guard.
- Исправлены ошибки ruff и mypy.
- CI теперь полностью зелёный.

---

## 7. Как обновлять MANIFEST

1. Добавлять новые файлы в соответствующие разделы.
2. Удалённые файлы переносить в «Удалено ранее».
3. Обновлять описания при изменении назначения файлов.

---
