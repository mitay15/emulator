# tools/check_project_structure.py
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_PACKAGES = [
    "aaps_emulator",
    "aaps_emulator/core",
    "aaps_emulator/runner",
    "aaps_emulator/visual",
    "aaps_emulator/tools",
]

REQUIRED_FILES = [
    "aaps_emulator/__init__.py",
    "aaps_emulator/core/__init__.py",
    "aaps_emulator/runner/__init__.py",
    "aaps_emulator/visual/__init__.py",
    "aaps_emulator/tools/__init__.py",
]


def check_init_files():
    print("Checking __init__.py files...")
    missing = []
    for f in REQUIRED_FILES:
        if not (ROOT / f).exists():
            missing.append(f)
    if missing:
        print("❌ Missing __init__.py:")
        for m in missing:
            print("   -", m)
    else:
        print("✔ All __init__.py files exist")


def check_package_dirs():
    print("\nChecking package directories...")
    missing = []
    for d in REQUIRED_PACKAGES:
        if not (ROOT / d).exists():
            missing.append(d)
    if missing:
        print("❌ Missing package directories:")
        for m in missing:
            print("   -", m)
    else:
        print("✔ All package directories exist")


def check_imports():
    print("\nChecking imports...")
    try:
        import aaps_emulator  # noqa: F401
        import aaps_emulator.core  # noqa: F401
        import aaps_emulator.runner  # noqa: F401
        print("✔ Imports OK")
    except Exception as e:
        print("❌ Import error:", e)


if __name__ == "__main__":
    print("=== PROJECT STRUCTURE CHECK ===")
    check_init_files()
    check_package_dirs()
    check_imports()
