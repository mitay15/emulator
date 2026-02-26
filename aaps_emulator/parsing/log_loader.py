import os
import zipfile
from typing import Any


def find_all_zip_logs(logs_dir: str = "logs") -> list[str]:
    if not os.path.exists(logs_dir):
        return []
    return [os.path.join(logs_dir, f) for f in os.listdir(logs_dir) if f.lower().endswith(".zip")]


def extract_zip(zip_path: str, out_dir: str | None = None) -> list[str]:
    if out_dir is None:
        out_dir = os.path.dirname(zip_path) or "."

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(out_dir)

    files: list[str] = []
    for root, _, filenames in os.walk(out_dir):
        for f in filenames:
            name = f.lower()
            if name.endswith(".log") or name.endswith(".txt"):
                files.append(os.path.join(root, f))

    return files


def load_log_blocks(path: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    ctx: list[str] = []

    with open(path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for line in lines:
        stripped = line.rstrip("\n")
        if "Result: RT(" in stripped:
            blocks.append({"context": ctx.copy(), "rt": stripped})
            ctx.clear()
        else:
            ctx.append(stripped)

    return blocks
