# aaps_emulator/tools/project_check.py
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = ROOT / "aaps_emulator"

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


def _add_root_to_sys_path() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def _py_files() -> List[Path]:
    return sorted(PKG_DIR.rglob("*.py"))


def _module_name_from_path(p: Path) -> str:
    rel = p.relative_to(ROOT)
    return ".".join(rel.with_suffix("").parts)


def check_init_files() -> bool:
    print("=== CHECK __init__.py FILES ===")
    missing = []
    for f in REQUIRED_FILES:
        if not (ROOT / f).exists():
            missing.append(f)
    if missing:
        print("❌ Missing __init__.py:")
        for m in missing:
            print("   -", m)
        return False
    print("✔ All __init__.py files exist")
    return True


def check_package_dirs() -> bool:
    print("\n=== CHECK PACKAGE DIRECTORIES ===")
    missing = []
    for d in REQUIRED_PACKAGES:
        if not (ROOT / d).exists():
            missing.append(d)
    if missing:
        print("❌ Missing package directories:")
        for m in missing:
            print("   -", m)
        return False
    print("✔ All package directories exist")
    return True


def check_top_level_imports() -> bool:
    print("\n=== CHECK TOP-LEVEL IMPORTS ===")
    _add_root_to_sys_path()
    try:
        import aaps_emulator  # noqa: F401
        import aaps_emulator.core  # noqa: F401
        import aaps_emulator.runner  # noqa: F401
        print("✔ Top-level imports OK")
        return True
    except Exception as e:
        print("❌ Import error:", e)
        return False


def check_all_modules_import() -> bool:
    print("\n=== CHECK ALL MODULE IMPORTS ===")
    _add_root_to_sys_path()
    files = _py_files()
    failures = []
    for p in files:
        mod = _module_name_from_path(p)
        try:
            importlib.import_module(mod)
            print(f"[OK]   {mod}")
        except Exception as e:
            failures.append((mod, str(e)))
            print(f"[FAIL] {mod} -> {e}")
    print("\nSummary:")
    print(f"Project root: {ROOT}")
    print(f"Total modules scanned: {len(files)}")
    print(f"Failures: {len(failures)}")
    if failures:
        print("\nFailed modules (module : error):")
        for m, e in failures:
            print(m, ":", e)
        return False
    return True


def main() -> None:
    ok1 = check_init_files()
    ok2 = check_package_dirs()
    ok3 = check_top_level_imports()
    ok4 = check_all_modules_import()
    print("\n=== FINAL RESULT ===")
    if ok1 and ok2 and ok3 and ok4:
        print("✔ PROJECT STRUCTURE OK")
        raise SystemExit(0)
    else:
        print("❌ PROJECT STRUCTURE / IMPORTS ISSUES")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
