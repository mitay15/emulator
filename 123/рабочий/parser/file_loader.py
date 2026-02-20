import os
import gzip
import zipfile


class LogFileLoader:
    """
    Универсальный загрузчик:
    - читает ZIP с любым именем
    - читает все файлы внутри ZIP
    - читает любые .txt, .log, .gz
    - читает любые файлы, содержащие APS-данные
    """

    def __init__(self, folder: str):
        self.folder = folder

    def iter_log_files(self):
        """
        Возвращает ВСЕ файлы:
        - любые ZIP
        - любые .txt, .log, .gz
        - любые файлы внутри ZIP
        """
        for root, _, files in os.walk(self.folder):
            for name in files:
                path = os.path.join(root, name)

                # ZIP — читаем всегда
                if name.lower().endswith(".zip"):
                    yield ("zip", path)
                    continue

                # любые текстовые файлы
                if (
                    name.lower().endswith(".txt")
                    or name.lower().endswith(".log")
                    or name.lower().endswith(".gz")
                    or ".log" in name.lower()  # AndroidAPS.2026-01-14.0.log
                    or ".txt" in name.lower()  # странные имена типа "[.txt"
                ):
                    yield ("file", path)

    def iter_log_lines(self):
        """
        Возвращает строки из всех файлов.
        """
        for ftype, path in self.iter_log_files():

            # -----------------------------
            # ZIP-файл — читаем ВСЁ внутри
            # -----------------------------
            if ftype == "zip":
                try:
                    with zipfile.ZipFile(path, "r") as z:
                        for fname in z.namelist():
                            # читаем любые файлы внутри ZIP
                            with z.open(fname, "r") as f:
                                try:
                                    for line in f:
                                        yield line.decode("utf-8", errors="ignore").strip()
                                except Exception:
                                    pass
                except Exception as e:
                    print(f"[ZIP ERROR] {path}: {e}")
                continue

            # -----------------------------
            # Обычный файл
            # -----------------------------
            if path.endswith(".gz"):
                opener = gzip.open
                mode = "rt"
            else:
                opener = open
                mode = "r"

            try:
                with opener(path, mode, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        yield line.strip()
            except Exception as e:
                print(f"[FILE ERROR] {path}: {e}")
