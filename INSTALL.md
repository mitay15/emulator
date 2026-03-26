-

# 📦 **INSTALL.md — Установка и запуск AAPS Emulator**

Этот документ описывает, как установить, запустить и проверить Python‑пакет **AAPS Emulator** — полноценную реализацию алгоритма AUTOISF и связанных модулей AndroidAPS.

---

# 🚀 1. Требования

### ✔ Python 3.10–3.12  
### ✔ Git (опционально)  
### ✔ pip + venv  
### ✔ ОС: Windows / macOS / Linux  

---

# 📁 2. Структура проекта

После клонирования или скачивания проект выглядит так:

```
AAPS-Emulator/
│
├── pyproject.toml
├── README.md
├── run_all.py
├── run_tests.py
│
└── aaps_emulator/
    ├── core/
    ├── runner/
    ├── tools/
    ├── tests/
    └── data/
```

Папка `aaps_emulator/` — это **Python‑пакет**, который устанавливается через `pip install -e .`.

---

# 🧰 3. Установка

## 3.1. Создать виртуальное окружение

Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3.2. Установить пакет в режиме разработки

Находясь в корне проекта (`AAPS-Emulator/`):

```bash
pip install -e .
```

Это установит пакет `aaps_emulator` и все зависимости из `pyproject.toml`.

---

# 🧪 4. Проверка установки

## 4.1. Запуск тестов

```bash
python run_tests.py
```

или напрямую:

```bash
pytest -q
```

Если всё прошло успешно — пакет установлен корректно.

---

# ▶️ 5. Запуск полного пайплайна

Полный анализ логов, построение heatmap, графиков и интерактивного HTML‑отчёта:

```bash
python run_all.py
```

После выполнения автоматически откроется:

```
aaps_emulator/data/reports/html/parity_report_interactive.html
```

---

# 🧩 6. Запуск отдельных модулей

## 6.1. Сравнение Python ↔ AAPS

```bash
python -m aaps_emulator.runner.compare_runner --report
```

## 6.2. Генерация интерактивного отчёта

```bash
python -m aaps_emulator.tools.run_full_report --open
```

## 6.3. Генерация inputs из логов

```bash
python -m aaps_emulator.tools.generate_inputs_from_logs --logs aaps_emulator/data/logs
```

## 6.4. Диагностика одного mismatch‑блока

```bash
python -m aaps_emulator.tools.debug_one_block --file aaps_emulator/data/cache/mismatch_block_01234.json
```

---

# 📚 7. Импорты внутри проекта

Теперь, когда проект — пакет, все импорты должны быть пакетными:

```python
from aaps_emulator.core.autoisf_pipeline import run_autoisf_pipeline
from aaps_emulator.runner.compare_runner import compare_logs
from aaps_emulator.tools.plot_predbg_diff import plot_predbg_diff
```

---

# 🧹 8. Очистка кеша и отчётов

Удалить все временные файлы:

```
aaps_emulator/data/cache/
aaps_emulator/data/reports/
```

---

# 🎯 9. Полезные советы

- Всегда активируй виртуальное окружение перед запуском.
- Если меняешь структуру пакета — переустанови:

```bash
pip install -e .
```

- Если отчёт не открывается — проверь путь:

```
aaps_emulator/data/reports/html/parity_report_interactive.html
```

---
