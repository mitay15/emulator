# aaps_emulator/gui/widgets/signals_view.py
import logging
import os
from datetime import datetime

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)


class SignalsView(QtWidgets.QWidget):
    """
    Полный файл SignalsView с увеличенными кнопками и иконками.
    """

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)

        # Figure / Canvas
        self.fig, self.axes = plt.subplots(5, 1, figsize=(10, 8), sharex=True)
        self.canvas = FigureCanvasQTAgg(self.fig)
        layout.addWidget(self.canvas)

        # Toolbar (zoom/pan)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        layout.addWidget(self.toolbar)

        # Buttons row
        btn_layout = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Сохранить график (PNG)")
        self.save_btn.setToolTip("Сохранить текущие графики Signals в PNG-файл")
        # try to set icon
        try:
            self.save_btn.setIcon(QtGui.QIcon(self._icon_path("save.png")))
            self.save_btn.setIconSize(QtCore.QSize(20, 20))
        except Exception:
            logger.exception("signals_view: suppressed exception")

        # make button larger
        self.save_btn.setFixedHeight(36)
        font = self.save_btn.font()
        font.setPointSize(10)
        self.save_btn.setFont(font)
        self.save_btn.setStyleSheet("padding-left:8px; padding-right:8px;")

        btn_layout.addWidget(self.save_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.save_btn.clicked.connect(self.export_png)

        # interactive state
        self._rows = []
        self._inputs = []
        self._ts_all = []
        self._on_select = None
        self._selected_idx = None

        # connect mpl events
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_press_event", self._on_click)

        # tooltip annotation (shared across axes)
        self._annot = self.axes[0].annotate(
            "",
            xy=(0, 0),
            xytext=(15, 15),
            textcoords="offset points",
            bbox={"boxstyle": "round", "fc": "w"},
            arrowprops={"arrowstyle": "->"},
        )
        self._annot.set_visible(False)

    def _icon_path(self, name):
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "icons"))
        return os.path.join(base, name)

    def update_signals(self, rows, inputs, selected_idx, on_select_callback=None):
        self._rows = rows
        self._inputs = inputs
        self._on_select = on_select_callback
        self._selected_idx = selected_idx

        # timestamps and datetimes
        self._ts_all = [r.get("ts_s", 0) for r in rows]
        dt = [datetime.fromtimestamp(int(t)) for t in self._ts_all] if self._ts_all else []

        # signals arrays (safe extraction)
        bg = [inp["glucose_status"].glucose for inp in inputs]
        iob = [inp["iob_array"][0].iob if inp["iob_array"] else 0 for inp in inputs]
        cob = [inp["meal"].meal_cob for inp in inputs]
        autosens = [inp["autosens"].ratio for inp in inputs]
        isf = [inp["profile"].sens for inp in inputs]

        # clear axes
        for ax in self.axes:
            ax.clear()

        # plot
        if dt:
            self.axes[0].plot(dt, bg, label="BG (mmol/L)", color="#00aaff", picker=5)
            self.axes[1].plot(dt, iob, label="IOB (U)", color="#ff66cc", picker=5)
            self.axes[2].plot(dt, cob, label="COB (g)", color="#ffb74d", picker=5)
            self.axes[3].plot(dt, autosens, label="Autosens (ratio)", color="#ffd54f", picker=5)
            self.axes[4].plot(dt, isf, label="ISF (mmol/U)", color="#8bc34a", picker=5)
        else:
            for ax in self.axes:
                ax.text(
                    0.5,
                    0.5,
                    "No data",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )

        # legends and grid
        for ax in self.axes:
            ax.legend(loc="upper left", fontsize=8)
            ax.grid(True, alpha=0.2)

        # format x-axis as date/time on bottom axis
        self.axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator())
        self.axes[-1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(mdates.AutoDateLocator()))
        self.axes[-1].set_xlabel("Дата / Время")

        # draw vertical cursor for selected_idx
        if self._selected_idx is not None and dt:
            try:
                pos = next(i for i, r in enumerate(rows) if r["idx"] == self._selected_idx)
                x_sel = dt[pos]
                for ax in self.axes:
                    ax.axvline(x_sel, color="#ff5252", linestyle="--", alpha=0.9)
            except StopIteration:
                logger.exception("signals_view: selected index not found")

        self.fig.tight_layout()
        self.canvas.draw()

    def _on_motion(self, event):
        if event.inaxes is None:
            if self._annot.get_visible():
                self._annot.set_visible(False)
                self.canvas.draw_idle()
            return

        x = event.xdata
        if x is None or not self._ts_all:
            return

        ts = np.array(self._ts_all)
        idx = int((np.abs(ts - x)).argmin()) if ts.size else 0
        if idx < 0 or idx >= len(self._rows):
            return

        try:
            inp = self._inputs[idx]
            row = self._rows[idx]
            text = (
                f"#{row['idx']}  {datetime.fromtimestamp(row['ts_s']).strftime('%Y-%m-%d %H:%M')}\n"
                f"BG: {inp['glucose_status'].glucose:.2f} mmol/L\n"
                f"Δ: {inp['glucose_status'].delta:.3f} mmol/5min\n"
                f"IOB: {inp['iob_array'][0].iob if inp['iob_array'] else 0:.2f} U\n"
                f"COB: {inp['meal'].meal_cob:.1f} g\n"
                f"Autosens: {inp['autosens'].ratio:.3f}\n"
                f"ISF: {inp['profile'].sens:.2f} mmol/U"
            )
        except Exception:
            text = "no data"

        try:
            x_dt = datetime.fromtimestamp(self._ts_all[idx])
            self._annot.xy = (x_dt, event.ydata)
        except Exception:
            self._annot.xy = (event.xdata, event.ydata)

        self._annot.set_text(text)
        self._annot.set_visible(True)
        self.canvas.draw_idle()

    def _on_click(self, event):
        if event.inaxes is None:
            return
        x = event.xdata
        if x is None or not self._ts_all:
            return
        ts = np.array(self._ts_all)
        idx = int((np.abs(ts - x)).argmin())
        if 0 <= idx < len(self._rows):
            global_idx = self._rows[idx]["idx"]
            if self._on_select:
                self._on_select(global_idx)

    def export_png(self):
        try:
            fname = "signals_export.png"
            self.fig.savefig(fname, dpi=150)
            print(f"[SignalsView] saved {fname}")
        except Exception as e:
            print(f"[SignalsView] export failed: {e}")
