# run_tests.py
import sys

import pytest

if __name__ == "__main__":
    args = [
        "-q",
        "--maxfail=1",
        "--disable-warnings",
        "tests",
    ]
    sys.exit(pytest.main(args))
