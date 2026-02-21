# aaps_emulator/gui/widgets/filters_bar.py
from PyQt6 import QtCore, QtGui, QtWidgets


class FiltersBar(QtWidgets.QWidget):
    filters_changed = QtCore.pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # checkboxes with clear labels and tooltips
        self.cb_autoisf = QtWidgets.QCheckBox("Показывать только AutoISF")
        self.cb_autoisf.setToolTip(
            "Показывать только RT, где AutoISF был активен (autosens.ratio != 1.0)"
        )

        self.cb_smb = QtWidgets.QCheckBox("Показывать только SMB")
        self.cb_smb.setToolTip(
            "Показывать только RT, где есть SMB (heuristic: insulinReq > 0)"
        )

        self.cb_high_delta = QtWidgets.QCheckBox("Показывать только High Δ")
        self.cb_high_delta.setToolTip(
            "Показывать только RT с большой скоростью изменения глюкозы (|Δ| ≥ 0.5 mmol/L)"
        )

        layout.addWidget(self.cb_autoisf)
        layout.addWidget(self.cb_smb)
        layout.addWidget(self.cb_high_delta)

        # ZIP filter
        layout.addWidget(QtWidgets.QLabel("Фильтр ZIP:"))
        self.zip_input = QtWidgets.QLineEdit()
        self.zip_input.setPlaceholderText("часть имени zip-файла")
        self.zip_input.setToolTip(
            "Введите часть имени ZIP-файла (регистронезависимо), чтобы показать только записи из этого архива"
        )
        self.zip_input.setFixedWidth(220)
        layout.addWidget(self.zip_input)

        # debounce timer for zip input (300 ms)
        self._zip_debounce = QtCore.QTimer(self)
        self._zip_debounce.setSingleShot(True)
        self._zip_debounce.setInterval(300)
        self.zip_input.textChanged.connect(self._on_zip_text_changed)
        self._zip_debounce.timeout.connect(self.emit_filters)

        # time range with explicit enable checkbox
        self.cb_time_enable = QtWidgets.QCheckBox("Использовать временной диапазон")
        self.cb_time_enable.setToolTip("Включите, чтобы применить фильтр по времени")
        layout.addWidget(self.cb_time_enable)

        layout.addWidget(QtWidgets.QLabel("С:"))
        self.time_from = QtWidgets.QDateTimeEdit()
        self.time_from.setCalendarPopup(True)
        self.time_from.setToolTip(
            "Начало временного диапазона (используется только если включён флажок)"
        )
        self.time_from.setFixedWidth(160)
        layout.addWidget(self.time_from)

        layout.addWidget(QtWidgets.QLabel("По:"))
        self.time_to = QtWidgets.QDateTimeEdit()
        self.time_to.setCalendarPopup(True)
        self.time_to.setToolTip(
            "Конец временного диапазона (используется только если включён флажок)"
        )
        self.time_to.setFixedWidth(160)
        layout.addWidget(self.time_to)

        # Apply and Clear buttons with icons and tooltips — увеличенный размер
        self.apply_btn = QtWidgets.QPushButton("Применить фильтры")
        self.apply_btn.setToolTip("Применить текущие фильтры к Timeline")
        self.clear_btn = QtWidgets.QPushButton("Сбросить фильтры")
        self.clear_btn.setToolTip("Сбросить все фильтры и показать все записи")

        # set icons (icons must be placed in gui/icons/)
        try:
            self.apply_btn.setIcon(QtGui.QIcon(self._icon_path("apply.png")))
            self.clear_btn.setIcon(QtGui.QIcon(self._icon_path("clear.png")))
        except Exception:
            pass

        # Bigger buttons: height, padding, font
        btn_height = 36
        self.apply_btn.setFixedHeight(btn_height)
        self.clear_btn.setFixedHeight(btn_height)
        font = self.apply_btn.font()
        font.setPointSize(10)
        self.apply_btn.setFont(font)
        self.clear_btn.setFont(font)

        icon_size = QtCore.QSize(20, 20)
        self.apply_btn.setIconSize(icon_size)
        self.clear_btn.setIconSize(icon_size)

        # add style for padding
        self.apply_btn.setStyleSheet("padding-left:8px; padding-right:8px;")
        self.clear_btn.setStyleSheet("padding-left:8px; padding-right:8px;")

        layout.addWidget(self.apply_btn)
        layout.addWidget(self.clear_btn)
        layout.addStretch()

        # connections: emit filters on change (immediate feedback)
        self.cb_autoisf.stateChanged.connect(self.emit_filters)
        self.cb_smb.stateChanged.connect(self.emit_filters)
        self.cb_high_delta.stateChanged.connect(self.emit_filters)
        self.cb_time_enable.stateChanged.connect(self.emit_filters)
        self.time_from.dateTimeChanged.connect(self._on_time_changed)
        self.time_to.dateTimeChanged.connect(self._on_time_changed)
        self.apply_btn.clicked.connect(self.emit_filters)
        self.clear_btn.clicked.connect(self._on_clear)

    def _icon_path(self, name):
        import os

        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "icons"))
        return os.path.join(base, name)

    def _on_zip_text_changed(self, _):
        # restart debounce timer
        self._zip_debounce.start()

    def _on_time_changed(self, _):
        # only emit if time filter enabled
        if self.cb_time_enable.isChecked():
            self.emit_filters()

    def _on_clear(self):
        self.cb_autoisf.setChecked(False)
        self.cb_smb.setChecked(False)
        self.cb_high_delta.setChecked(False)
        self.zip_input.clear()
        self.cb_time_enable.setChecked(False)
        # reset times to minimum (no range)
        self.time_from.setDateTime(self.time_from.minimumDateTime())
        self.time_to.setDateTime(self.time_to.minimumDateTime())
        self.emit_filters()

    def emit_filters(self):
        filters = {
            "autoisf_on": self.cb_autoisf.isChecked(),
            "smb": self.cb_smb.isChecked(),
            "high_delta": self.cb_high_delta.isChecked(),
            "zip_name": self.zip_input.text().strip() or None,
            "time_range": None,
        }

        if self.cb_time_enable.isChecked():
            try:
                t_from = int(self.time_from.dateTime().toSecsSinceEpoch())
                t_to = int(self.time_to.dateTime().toSecsSinceEpoch())
                if t_from <= t_to:
                    filters["time_range"] = (t_from, t_to)
            except Exception:
                filters["time_range"] = None

        # debug print so you can see events in console
        print(f"[FiltersBar] emit_filters -> {filters}")
        self.filters_changed.emit(filters)
