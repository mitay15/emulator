# aaps_emulator/gui/main_qt.py

from analysis.compare_runner import run_compare_on_all_logs
from gui.widgets.compare_view import CompareView
from gui.widgets.context_view import ContextView
from gui.widgets.details_view import DetailsView
from gui.widgets.filters_bar import FiltersBar
from gui.widgets.signals_view import SignalsView
from gui.widgets.timeline_view import TimelineView
from PyQt6 import QtGui, QtWidgets


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

        self.tabs = QtWidgets.QTabWidget()
        self.signals_tab = SignalsView()
        self.context_tab = ContextView()
        self.details_tab = DetailsView()
        self.compare_tab = CompareView()

        self.tabs.addTab(self.signals_tab, "Signals")
        self.tabs.addTab(self.context_tab, "Context")
        self.tabs.addTab(self.details_tab, "Details")
        self.tabs.addTab(self.compare_tab, "Compare")

        right_layout.addWidget(self.tabs)
        main_layout.addLayout(right_layout, 5)

        # load data
        self.rows, self.blocks, self.inputs = run_compare_on_all_logs("logs")

        # populate timeline
        self.timeline.load(self.rows, self.inputs)

        # connect signals
        self.timeline.rt_selected.connect(self.on_rt_selected)
        self.filter_bar.filters_changed.connect(self.on_filters_changed)

        # initial selection: first item if exists
        if self.rows:
            first_idx = self.rows[0]["idx"]
            self.select_rt(first_idx)

    def on_rt_selected(self, idx):
        # idx is global index
        print(f"[MainWindow] on_rt_selected -> {idx}")
        try:
            pos = next(i for i, r in enumerate(self.rows) if r["idx"] == idx)
        except StopIteration:
            print(f"[MainWindow] on_rt_selected: idx {idx} not found in rows")
            return
        block = self.blocks[pos]
        inp = self.inputs[pos]

        # update views; pass callback so signals can call back to select timeline
        self.signals_tab.update_signals(self.rows, self.inputs, idx, on_select_callback=self.select_rt)
        self.context_tab.update_context(block)
        self.details_tab.update_details(inp, block)
        # update compare with full rows and selected idx
        self.compare_tab.update_compare(self.rows, selected_idx=idx)

    def select_rt(self, global_idx):
        """
        Called by SignalsView when user clicks on a point.
        Also used internally to programmatically select timeline item.
        """
        self.timeline.select_by_idx(global_idx)
        # also trigger on_rt_selected to refresh views
        self.on_rt_selected(global_idx)

    def on_filters_changed(self, filters):
        # debug: покажем в консоли, что MainWindow получил фильтры
        print(f"[MainWindow] on_filters_changed -> {filters}")
        # apply filters to timeline
        self.timeline.apply_filters(self.rows, self.inputs, filters)


def enable_light_theme(app):
    """
    Устанавливает светлую тему с нейтральными контрастными цветами.
    """
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, QtGui.QColor("#ffffff"))
    palette.setColor(palette.ColorRole.Base, QtGui.QColor("#ffffff"))
    palette.setColor(palette.ColorRole.Text, QtGui.QColor("#111111"))
    palette.setColor(palette.ColorRole.Button, QtGui.QColor("#f0f0f0"))
    palette.setColor(palette.ColorRole.ButtonText, QtGui.QColor("#111111"))
    palette.setColor(palette.ColorRole.Highlight, QtGui.QColor("#1976d2"))
    palette.setColor(palette.ColorRole.HighlightedText, QtGui.QColor("#ffffff"))
    app.setPalette(palette)

    # Optional: tweak default font sizes for readability
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)


def main():
    app = QtWidgets.QApplication([])
    enable_light_theme(app)
    w = MainWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
