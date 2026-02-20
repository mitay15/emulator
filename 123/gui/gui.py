import tkinter as tk
from tkinter import filedialog, messagebox
import threading

from main import process_logs


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AAPS 3.4 JSON Analyzer & Emulator")
        self.geometry("400x200")

        self.folder = tk.StringVar()

        tk.Label(self, text="Папка с логами:").pack(pady=5)
        tk.Entry(self, textvariable=self.folder, width=40).pack(pady=5)

        tk.Button(self, text="Выбрать папку", command=self.choose_folder).pack(pady=5)
        tk.Button(self, text="Запустить анализ", command=self.run_analysis).pack(pady=10)

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder.set(folder)

    def run_analysis(self):
        if not self.folder.get():
            messagebox.showerror("Ошибка", "Выберите папку с логами")
            return

        t = threading.Thread(target=self._run)
        t.daemon = True
        t.start()

    def _run(self):
        try:
            process_logs(self.folder.get())
            messagebox.showinfo("Готово", "Анализ завершён. Смотри консоль, CSV и графики.")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))


def run_gui():
    app = App()
    app.mainloop()
