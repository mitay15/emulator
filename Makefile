# -----------------------------------------
#  AAPS Emulator — Developer Convenience
# -----------------------------------------

# -----------------------
#  Тесты
# -----------------------

test:
    pytest -q

testv:
    pytest -vv

smoke:
    pytest -m smoke -vv

integration:
    pytest -m integration -vv

visual:
    pytest -m visual -vv

unit:
    pytest -m unit -vv

# -----------------------
#  Основные команды
# -----------------------

ga:
    python run.py ga

gui:
    python run.py gui

compare:
    python run.py compare

inputs:
    python run.py inputs

# -----------------------
#  Форматирование и линтинг
# -----------------------

format:
    ruff check --fix .
    black .
    autoflake --in-place --remove-unused-variables --remove-all-unused-imports -r .

lint:
    ruff check .
    black --check .
    autoflake -r .

# -----------------------
#  Документация
# -----------------------

docs:
    pdoc -o docs aaps_emulator

# -----------------------
#  Очистка
# -----------------------

clean:
    rm -rf __pycache__ */__pycache__
    rm -rf .pytest_cache
    rm -rf dist build
    rm -rf data/cache/*
    rm -rf data/reports/*

# -----------------------
#  Релиз
# -----------------------

release:
    @if [ -z "$(VERSION)" ]; then \
        echo "Usage: make release VERSION=x.y.z"; exit 1; \
    fi
    git tag v$(VERSION)
    git push origin v$(VERSION)
