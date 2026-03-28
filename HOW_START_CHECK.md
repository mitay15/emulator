### Краткое описание проекта и как всё правильно запускать

Ниже — пошаговая инструкция от **установки окружения** до **полной проверки** (линтеры, тесты, генерация входов, валидация). Выполняй команды из корня репозитория `C:\Users\IngPPO1\Desktop\AAPS-Emulator`.

---

### 1 Установка и подготовка окружения
- **Создать виртуальное окружение** (если ещё нет):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
- **Обновить pip и установить зависимости проекта**:
```powershell
python -m pip install --upgrade pip
pip install -e .
pip install -r requirements.txt || true
```
- **Рекомендация по CRLF на Windows**:
```powershell
git config core.autocrlf true
```

---

### 2 Линтеры и pre-commit
- **Запустить pre-commit (он применит ruff/autoflake и т.д.)**:
```powershell
pre-commit run --all-files
```
- **Если ruff не в PATH, установить и запустить через python -m**:
```powershell
pip install ruff
python -m ruff check .
```
- **После автоматических правок**:
```powershell
git add -A
git commit -m "style: apply linter fixes"
```

---

### 3 Тесты
- **Запуск всех тестов**:
```powershell
pytest -q
```
- **Если падает тест — запустить конкретный тест для отладки**:
```powershell
pytest path/to/test_file.py::test_name -q -k test_name
```

---

### 4 Генерация входов из логов и валидация
- **Генерация inputs в кэш**:
```powershell
python -m aaps_emulator.tools.generate_inputs_from_logs aaps_emulator\data\logs --out data\cache
```
- **Проверить, что файлы создались**:
```powershell
Get-ChildItem -Path data\cache -File | Select-Object Name, Length
```
- **Запустить встроенную валидацию**:
```powershell
python -m aaps_emulator.tools.validate_all
```

---

### 5 Скрипт полной проверки (check_all.ps1)
- **Куда положить**: создать папку `scripts` в корне репозитория и сохранить файл `scripts/check_all.ps1` (я уже дал содержимое ранее).  
- **Как запускать** (с активированным venv):
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_all.ps1
```
- **Что делает**: выполняет pre-commit, ruff, pytest, генерацию входов, validate_all и выводит первые строки сгенерированного JSON в `scripts/check_all.log`.

---

### 6 Git и .gitignore
- **Проверить статус и закоммитить изменения**:
```powershell
git add -A
git commit -m "fix: ... (описание изменений)"
```
- **Если pre-commit изменил файлы — повтори add/commit.**  
- **Убедиться, что не добавлены большие артефакты**:
```powershell
git ls-files --stage | Select-String -Pattern "venv|data/cache|.zip|.log"
```
- **Рекомендованный .gitignore**: не игнорировать все `*.json`/`*.log` глобально; игнорировать конкретные сгенерированные папки `data/cache/` и `data/reports/`.

---

### 7 Что проверять в случае проблем
- **pre-commit/ruff** — исправляет стиль; если он ломает логику, откатить изменения и исправить вручную.  
- **pytest** — читать первый traceback; запустить тест локально.  
- **generate_inputs_from_logs** — если не создаёт файлов, проверь путь `aaps_emulator\data\logs` и расширения `.zip/.log/.json`.  
- **validate_all** — прислать первые 50–100 строк вывода, я помогу интерпретировать.

---
