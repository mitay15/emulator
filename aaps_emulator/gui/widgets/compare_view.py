# aaps_emulator/gui/widgets/compare_view.py
from datetime import datetime
import logging
import os

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)


class CompareView(QtWidgets.QWidget):
    """
    Полный файл CompareView с увеличенными кнопками и иконками.
    """

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)

        self.fig, self.ax = plt.subplots(figsize=(9, 4))
        self.canvas = FigureCanvasQTAgg(self.fig)
        layout.addWidget(self.canvas)

        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        layout.addWidget(self.toolbar)

        btn_layout = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Сохранить сравнение (PNG)")
        self.save_btn.setToolTip("Сохранить график сравнения AAPS vs PY в PNG-файл")
        try:
            self.save_btn.setIcon(QtGui.QIcon(self._icon_path("save.png")))
            self.save_btn.setIconSize(QtCore.QSize(20, 20))
        except Exception:
            logger.exception("compare_view: suppressed exception")

        # larger button
        self.save_btn.setFixedHeight(36)
        font = self.save_btn.font()
        font.setPointSize(10)
        self.save_btn.setFont(font)
        self.save_btn.setStyleSheet("padding-left:8px; padding-right:8px;")

        btn_layout.addWidget(self.save_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.save_btn.clicked.connect(self.export_png)

        # internal state
        self._rows = []
        self._selected_idx = None
        self._vline = None
        self._annot = None

    def _icon_path(self, name):
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "icons"))
        return os.path.join(base, name)

    def update_compare(self, rows, selected_idx=None):
        self._rows = rows
        self._selected_idx = selected_idx

        if not rows:
            self.ax.clear()
            self.ax.set_title("Нет данных")
            self.canvas.draw()
            return

        ts = [r.get("ts_s", 0) for r in rows]
        dt = [datetime.fromtimestamp(int(t)) for t in ts]
        aaps = [r.get("aaps_eventual") or 0.0 for r in rows]
        py = [r.get("py_eventual") or 0.0 for r in rows]

        self.ax.clear()
        self.ax.plot(dt, aaps, label="AAPS eventualBG (mmol/L)", color="#1976d2", linewidth=2)
        self.ax.plot(
            dt,
            py,
            label="PY eventualBG (mmol/L)",
            color="#ff9800",
            linewidth=2,
            linestyle="--",
        )

        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        self.ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(mdates.AutoDateLocator()))
        self.ax.set_xlabel("Дата / Время")
        self.ax.set_ylabel("eventualBG (mmol/L)")
        self.ax.legend()
        self.ax.grid(alpha=0.25)

        if self._selected_idx is not None:
            pos = next((i for i, r in enumerate(rows) if r["idx"] == self._selected_idx), None)
            if pos is not None:
                x_sel = dt[pos]
                if self._vline:
                    try:
                        self._vline.remove()
                    except Exception:
                        logger.exception("compare_view: suppressed exception")
                if self._annot:
                    try:
                        self._annot.remove()
                    except Exception:
                        logger.exception("compare_view: suppressed exception")

                self._vline = self.ax.axvline(x_sel, color="#d32f2f", linestyle="--", linewidth=1.5, alpha=0.9)
                txt = f"#{self._selected_idx}\nAAPS {aaps[pos]:.2f}\nPY {py[pos]:.2f}"
                y_top = max(max(aaps), max(py)) if aaps and py else 0
                self._annot = self.ax.annotate(
                    txt,
                    xy=(x_sel, y_top),
                    xytext=(10, -30),
                    textcoords="offset points",
                    bbox={"boxstyle": "round", "fc": "w", "alpha": 0.9},
                )

        self.fig.tight_layout()
        self.canvas.draw()

    def export_png(self):
        try:
            fname = "compare_export.png"
            self.fig.savefig(fname, dpi=150)
            print(f"[CompareView] saved {fname}")
        except Exception as e:
            print(f"[CompareView] export failed: {e}")
