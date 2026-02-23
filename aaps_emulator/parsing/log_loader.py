import os
import zipfile


def find_all_zip_logs(logs_dir="logs"):
    if not os.path.exists(logs_dir):
        return []
    return [
        os.path.join(logs_dir, f)
        for f in os.listdir(logs_dir)
        if f.lower().endswith(".zip")
    ]


def extract_zip(zip_path, out_dir=None):
    if out_dir is None:
        out_dir = os.path.dirname(zip_path) or "."

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(out_dir)

    files = []
    for root, _, filenames in os.walk(out_dir):
        for f in filenames:
            if f.lower().endswith(".log") or f.lower().endswith(".txt"):
                files.append(os.path.join(root, f))
    return files


def load_log_blocks(filepath):
    with open(filepath, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    blocks = []
    ctx = []

    for line in lines:
        if "Result: RT(" in line:
            blocks.append({"context": ctx, "rt": line.strip()})
            ctx = []
        else:
            ctx.append(line.rstrip("\n"))

    return blocks
