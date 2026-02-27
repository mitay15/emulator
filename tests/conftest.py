import json
from pathlib import Path

import pytest


@pytest.fixture
def load_json():
    def _load(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    return _load


@pytest.fixture
def logs_path():
    return Path("tests/data/logs")
