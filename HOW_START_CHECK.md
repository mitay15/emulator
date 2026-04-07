# 1. Установка окружения

### Создать и активировать виртуальное окружение
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Установить зависимости проекта
```powershell
python -m pip install --upgrade pip
pip install -e .
```

*(requirements.txt больше не нужен — зависимости в pyproject.toml)*

### Рекомендация для Windows (CRLF)
```powershell
git config core.autocrlf true
```

---

# 2. Линтеры и форматирование

Теперь всё делается через **Makefile**.

### Автоматическое исправление стиля
```powershell
make format
```

Выполняет:
- ruff (исправление)
- black (форматирование)
- autoflake (удаление мусора)

### Проверка стиля без исправления
```powershell
make lint
```

---

# 3. Тесты

### Запуск всех тестов
```powershell
make test
```

### Подробный вывод
```powershell
make testv
```

### Smoke‑тесты (Auto‑GA v3 + compare_runner)
```powershell
make smoke
```

### Интеграционные тесты
```powershell
make integration
```

### Визуальные тесты (heatmap, predBG)
```powershell
make visual
```

### Юнит‑тесты
```powershell
make unit
```

---

# 4. Генерация входов и сравнение с AAPS

### Генерация inputs_before_algo_block_*.json
```powershell
make inputs
```

### Сравнение Python ↔ AAPS логов
```powershell
make compare
```

*(заменяет старый validate_all и любые tools/\*.py)*

---

# 5. Запуск GUI

### Запуск Streamlit интерфейса
```powershell
make gui
```

Откроется визуальный интерфейс:

- predBG графики  
- AutoISF pipeline  
- Auto‑GA v3  
- отчёты  

---

# 6. Запуск Auto‑GA v3

### Запуск оптимизатора
```powershell
make ga
```

Покажет:

- прогресс поколений  
- лучший fitness  
- итоговые параметры  

---

# 7. Очистка проекта

### Удалить кэш, отчёты, временные файлы
```powershell
make clean
```

Удаляет:

- data/cache  
- data/reports  
- __pycache__  
- dist, build  
- .pytest_cache  

---

# 8. Генерация документации

### Создать HTML‑документацию API
```powershell
make docs
```

Документация появится в папке:

```
docs/
```

---

# 9. Релизы

### Создать git‑tag и отправить его на GitHub
```powershell
make release VERSION=0.2.0
```

GitHub Actions автоматически:

- соберёт wheel  
- создаст GitHub Release  
- прикрепит артефакты  

---

# 10. Git

### Проверить и закоммитить изменения
```powershell
git add -A
git commit -m "fix: ..."
git push
```

### Рекомендация по .gitignore
- не игнорировать все *.json  
- игнорировать только:
  - data/cache/
  - data/reports/

---

