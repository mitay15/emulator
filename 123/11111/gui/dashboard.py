import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QCheckBox, QFrame
)
from PyQt6.QtCore import Qt

import matplotlib

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from matplotlib.figure import Figure

from parser.timeline import TimelineBuilder
from analysis.plots import build_overview_layers


class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AAPS Emulator Dashboard (UTC)")
        self.setGeometry(200, 200, 1200, 800)

        main_layout = QHBoxLayout()
        left_panel = QVBoxLayout()
        right_panel = QVBoxLayout()

        self.label = QLabel("AAPS Dashboard (UTC)", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_panel.addWidget(self.label)

        btn_load = QPushButton("Load logs")
        btn_load.clicked.connect(self.load_logs)
        left_panel.addWidget(btn_load)

        self.time_filter = QComboBox()
        self.time_filter.addItems(["all", "night", "morning", "day", "evening"])
        left_panel.addWidget(self.time_filter)

        btn_overview = QPushButton("Build overview")
        btn_overview.clicked.connect(self.update_plot)
        left_panel.addWidget(btn_overview)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        left_panel.addWidget(sep)

        self.cb_bg = QCheckBox("BG")
        self.cb_pred = QCheckBox("PredBG")
        self.cb_iob = QCheckBox("IOB")
        self.cb_cob = QCheckBox("COB")
        self.cb_smb = QCheckBox("SMB")
        self.cb_bolus = QCheckBox("Bolus")
        self.cb_carbs = QCheckBox("Carbs")

        for cb in [
            self.cb_bg, self.cb_pred, self.cb_iob, self.cb_cob,
            self.cb_smb, self.cb_bolus, self.cb_carbs
        ]:
            cb.setChecked(True)
            cb.stateChanged.connect(self.update_plot)
            left_panel.addWidget(cb)

        left_panel.addStretch()
        
        self.btn_reset = QPushButton("Reset view")
        self.btn_reset.clicked.connect(self.update_plot)
        right_panel.addWidget(self.btn_reset)


        self.fig = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.fig)
        right_panel.addWidget(self.canvas)

        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        right_panel.addWidget(self.toolbar)

        main_layout.addLayout(left_panel, 1)
        main_layout.addLayout(right_panel, 4)

        self.setLayout(main_layout)

        self.events = []
        self.layers = {}

    def load_logs(self):
        tb = TimelineBuilder("data")
        self.events = tb.build_timeline()
        self.label.setText(f"Loaded events: {len(self.events)}")

    def filter_events(self):
        mode = self.time_filter.currentText()
        if mode == "all":
            return self.events

        from datetime import datetime, timezone

        def tod(ts):
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            h = dt.hour
            if 0 <= h < 6:
                return "night"
            if 6 <= h < 12:
                return "morning"
            if 12 <= h < 18:
                return "day"
            return "evening"

        return [e for e in self.events if tod(e.ts) == mode]

    def update_plot(self):
        if not self.events:
            return

        ev = self.filter_events()

        self.layers = build_overview_layers(self.fig, ev)
        self.apply_visibility()
        self.canvas.draw()

    def apply_visibility(self):
        if not self.layers:
            return

        self.layers["BG"].set_visible(self.cb_bg.isChecked())
        self.layers["PredBG"].set_visible(self.cb_pred.isChecked())
        self.layers["IOB"].set_visible(self.cb_iob.isChecked())
        self.layers["COB"].set_visible(self.cb_cob.isChecked())

        for obj in self.layers["SMB"]:
            obj.set_visible(self.cb_smb.isChecked())

        for obj in self.layers["Bolus"]:
            obj.set_visible(self.cb_bolus.isChecked())

        for obj in self.layers["Carbs"]:
            obj.set_visible(self.cb_carbs.isChecked())


def run_dashboard():
    app = QApplication(sys.argv)
    gui = Dashboard()
    gui.show()
    sys.exit(app.exec())
