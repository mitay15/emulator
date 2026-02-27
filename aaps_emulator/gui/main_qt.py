import shutil
import sys

from PyQt6 import QtGui, QtWidgets

from aaps_emulator.analysis.compare_runner import run_compare_on_all_logs
from aaps_emulator.config import LOGS_PATH, LOGS_ZIP
from aaps_emulator.gui.autoisf_report_widget import AutoISFReportWidget
from aaps_emulator.gui.widgets.compare_view import CompareView
from aaps_emulator.gui.widgets.context_view import ContextView
from aaps_emulator.gui.widgets.details_view import DetailsView
from aaps_emulator.gui.widgets.filters_bar import FiltersBar
from aaps_emulator.gui.widgets.signals_view import SignalsView
from aaps_emulator.gui.widgets.timeline_view import TimelineView
from aaps_emulator.tools.reports.autoisf_full_report import load_worst_rows


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AAPS AutoISF Emulator")
        self.resize(1600, 900)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        main_layout = QtWidgets.QHBoxLayout(central)

        left_layout = QtWidgets.QVBoxLayout()
        self.timeline = TimelineView()
        left_layout.addWidget(self.timeline)
        main_layout.addLayout(left_layout, 2)

        right_layout = QtWidgets.QVBoxLayout()
        self.filter_bar = FiltersBar()
        right_layout.addWidget(self.filter_bar)

        self.load_logs_btn = QtWidgets.QPushButton("Загрузить логи…")
        right_layout.addWidget(self.load_logs_btn)
        self.load_logs_btn.clicked.connect(self.load_logs_dialog)

        self.tabs = QtWidgets.QTabWidget()
        self.signals_tab = SignalsView()
        self.context_tab = ContextView()
        self.details_tab = DetailsView()
        self.compare_tab = CompareView()
        self.autoisf_tab = AutoISFReportWidget()

        self.tabs.addTab(self.signals_tab, "Signals")
        self.tabs.addTab(self.context_tab, "Context")
        self.tabs.addTab(self.details_tab, "Details")
        self.tabs.addTab(self.compare_tab, "Compare")
        self.tabs.addTab(self.autoisf_tab, "AutoISF Report")

        self.autoisf_tab.bridge.main_window = self
        self.autoisf_tab.report_rebuilt.connect(self.on_report_rebuilt)

        right_layout.addWidget(self.tabs)
        main_layout.addLayout(right_layout, 5)

        self.rows, self.blocks, self.inputs = run_compare_on_all_logs(str(LOGS_PATH))

        worst = set(load_worst_rows())
        for r in self.rows:
            r["is_worst"] = r["idx"] in worst

        self.timeline.load(self.rows, self.inputs)

        self.timeline.rt_selected.connect(self.on_rt_selected)
        self.filter_bar.filters_changed.connect(self.on_filters_changed)

        if self.rows:
            first_idx = self.rows[0]["idx"]
            self.select_rt(first_idx)

    def on_rt_selected(self, idx):
        print(f"[MainWindow] on_rt_selected -> {idx}")
        try:
            pos = next(i for i, r in enumerate(self.rows) if r["idx"] == idx)
        except StopIteration:
            print(f"[MainWindow] on_rt_selected: idx {idx} not found in rows")
            return
        block = self.blocks[pos]
        inp = self.inputs[pos]

        self.signals_tab.update_signals(self.rows, self.inputs, idx, on_select_callback=self.select_rt)
        self.context_tab.update_context(block)
        self.details_tab.update_details(inp, block)
        self.compare_tab.update_compare(self.rows, selected_idx=idx)

        self.autoisf_tab.highlight_idx(idx)

    def select_rt(self, global_idx):
        self.timeline.select_by_idx(global_idx)
        self.on_rt_selected(global_idx)

    def on_filters_changed(self, filters):
        print(f"[MainWindow] on_filters_changed -> {filters}")
        self.timeline.apply_filters(self.rows, self.inputs, filters)

    def load_logs_dialog(self):
        dlg = QtWidgets.QFileDialog(self)
        dlg.setNameFilter("ZIP files (*.zip)")
        dlg.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFile)

        if dlg.exec():
            selected = dlg.selectedFiles()[0]
            print("Выбран ZIP:", selected)

            shutil.copy(selected, LOGS_ZIP)

            self.rows, self.blocks, self.inputs = run_compare_on_all_logs(str(LOGS_PATH))

            worst = set(load_worst_rows())
            for r in self.rows:
                r["is_worst"] = r["idx"] in worst

            self.timeline.load(self.rows, self.inputs)
            if self.rows:
                self.select_rt(self.rows[0]["idx"])

    def on_report_rebuilt(self):
        print("Отчёт пересчитан — обновляем timeline")
        self.rows, self.blocks, self.inputs = run_compare_on_all_logs(str(LOGS_PATH))

        worst = set(load_worst_rows())
        for r in self.rows:
            r["is_worst"] = r["idx"] in worst

        self.timeline.load(self.rows, self.inputs)
        if self.rows:
            self.select_rt(self.rows[0]["idx"])


def enable_light_theme(app):
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, QtGui.QColor("#ffffff"))
    palette.setColor(palette.ColorRole.Base, QtGui.QColor("#ffffff"))
    palette.setColor(palette.ColorRole.Text, QtGui.QColor("#111111"))
    palette.setColor(palette.ColorRole.Button, QtGui.QColor("#f0f0f0"))
    palette.setColor(palette.ColorRole.ButtonText, QtGui.QColor("#111111"))
    palette.setColor(palette.ColorRole.Highlight, QtGui.QColor("#1976d2"))
    palette.setColor(palette.ColorRole.HighlightedText, QtGui.QColor("#ffffff"))
    app.setPalette(palette)

    font = app.font()
    font.setPointSize(10)
    app.setFont(font)


def main():
    if not sys.argv:
        sys.argv = ["aaps_emulator"]

    app = QtWidgets.QApplication(sys.argv)
    enable_light_theme(app)
    w = MainWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
