# aaps_emulator/tools/check_imports.py
import sys
from pathlib import Path
import importlib

# Корень проекта: два уровня выше этого файла
ROOT = Path(__file__).resolve().parents[2]
# Путь к пакету внутри репозитория
PKG_DIR = ROOT / "aaps_emulator"

# Добавляем корень проекта в sys.path, чтобы импорты aaps_emulator.* работали
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def py_files():
    return sorted(PKG_DIR.rglob("*.py"))

def module_name_from_path(p: Path):
    rel = p.relative_to(ROOT)
    return ".".join(rel.with_suffix("").parts)

def try_import(module_name):
    try:
        importlib.import_module(module_name)
        return True, None
    except Exception as e:
        return False, str(e)

def main():
    files = py_files()
    failures = []
    for p in files:
        mod = module_name_from_path(p)
        ok, err = try_import(mod)
        if not ok:
            failures.append((mod, err))
            print(f"[FAIL] {mod} -> {err}")
        else:
            print(f"[OK]   {mod}")
    print("\nSummary:")
    print(f"Project root: {ROOT}")
    print(f"Total modules scanned: {len(files)}")
    print(f"Failures: {len(failures)}")
    if failures:
        print("\nFailed modules (module : error):")
        for m, e in failures:
            print(m, ":", e)

if __name__ == '__main__':
    main()
