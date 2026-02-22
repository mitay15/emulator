# aaps_emulator/gui/widgets/timeline_view.py
from datetime import datetime

from PyQt6 import QtCore, QtGui, QtWidgets


class TimelineView(QtWidgets.QWidget):
    rt_selected = QtCore.pyqtSignal(int)  # emits global idx

    def __init__(self):
        super().__init__()
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(4)

        # header: title + active filters label
        header_layout = QtWidgets.QHBoxLayout()
        self.title_label = QtWidgets.QLabel("<b>Timeline</b>")
        self.title_label.setToolTip("Список RT (результатов). Клик — выбрать RT.")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()
        self.filters_label = QtWidgets.QLabel("Фильтры: (нет)")
        self.filters_label.setStyleSheet("color: #444444;")
        self.filters_label.setToolTip("Показаны активные фильтры")
        header_layout.addWidget(self.filters_label)

        v.addLayout(header_layout)

        # the actual list
        self.list = QtWidgets.QListWidget()
        self.list.currentRowChanged.connect(self._on_row_changed)
        self.list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        v.addWidget(self.list)

        # internal state
        self._all_rows = []
        self._inputs = []
        self._index_map = []

    def load(self, rows, inputs):
        """
        rows: full list of row dicts (as returned by compare_runner)
        inputs: full list of inputs (same order)
        """
        self._all_rows = rows
        self._inputs = inputs
        indices = [r["idx"] for r in rows]
        self._rebuild_items(indices)
        self._update_filters_label({})

    def apply_filters(self, rows, inputs, filters):
        """
        rows, inputs: full lists (unfiltered)
        filters: dict with keys autoisf_on, smb, high_delta, zip_name, time_range
        """
        self._all_rows = rows
        self._inputs = inputs

        visible = []
        for _pos, (r, inp) in enumerate(zip(rows, inputs, strict=True)):
            autosens = inp.get("autosens")
            gs = inp.get("glucose_status")
            rt = inp.get("rt")

            if filters.get("autoisf_on"):
                if getattr(autosens, "ratio", 1.0) == 1.0:
                    continue
            if filters.get("smb"):
                if not (rt.get("insulinReq") and rt.get("insulinReq") > 0):
                    continue
            if filters.get("high_delta"):
                if not gs or abs(gs.delta) < 0.5:
                    continue
            tr = filters.get("time_range")
            if tr:
                ts = r.get("ts_s", 0)
                if ts < tr[0] or ts > tr[1]:
                    continue
            zipf = filters.get("zip_name")
            if zipf:
                if zipf.lower() not in r.get("zip_name", "").lower():
                    continue

            visible.append(r["idx"])

        self._rebuild_items(visible)
        self._update_filters_label(filters)

    def _rebuild_items(self, indices):
        self.list.clear()
        self._index_map = []

        idx_to_pos = {r["idx"]: i for i, r in enumerate(self._all_rows)}

        for idx in indices:
            pos = idx_to_pos.get(idx)
            if pos is None:
                continue
            row = self._all_rows[pos]
            ts = row.get("ts_s", 0)
            try:
                dt = datetime.fromtimestamp(int(ts))
                ts_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                ts_str = str(ts)

            aaps_ev = row.get("aaps_eventual", 0.0) or 0.0
            py_ev = row.get("py_eventual", 0.0) or 0.0
            item_text = f"#{idx}  {ts_str}  AAPS {aaps_ev:.2f}  PY {py_ev:.2f}  [{row.get('zip_name', '')}]"
            item = QtWidgets.QListWidgetItem(item_text)

            inp = self._inputs[pos] if pos < len(self._inputs) else None
            if inp:
                autosens = inp.get("autosens")
                gs = inp.get("glucose_status")
                if getattr(autosens, "ratio", 1.0) != 1.0:
                    item.setBackground(QtGui.QColor("#e8f4ff"))
                if gs and abs(gs.delta) >= 0.5:
                    item.setForeground(QtGui.QColor("#b35900"))

            self.list.addItem(item)
            self._index_map.append(idx)

    def _on_row_changed(self, row):
        if row < 0 or row >= len(self._index_map):
            return
        idx = self._index_map[row]
        print(f"[TimelineView] user selected list pos={row} -> global idx={idx}")
        self.rt_selected.emit(idx)

    def select_by_idx(self, idx):
        """
        Programmatically select item by global idx.
        If idx is not visible due to filters, temporarily ensure it is visible and select it.
        """
        try:
            pos = self._index_map.index(idx)
            self.list.setCurrentRow(pos)
            return
        except ValueError:
            # not visible — try to insert it at top of list (make visible)
            print(
                f"[TimelineView] select_by_idx: idx {idx} not visible, making it visible"
            )
            all_indices = [idx] + [
                i for i in (r["idx"] for r in self._all_rows) if i != idx
            ]
            self._rebuild_items(all_indices)
            self.list.setCurrentRow(0)
            return

    def _update_filters_label(self, filters):
        parts = []
        if not filters:
            self.filters_label.setText("Фильтры: (нет)")
            return
        if filters.get("autoisf_on"):
            parts.append("AutoISF")
        if filters.get("smb"):
            parts.append("SMB")
        if filters.get("high_delta"):
            parts.append("High Δ")
        if filters.get("zip_name"):
            parts.append(f"ZIP='{filters.get('zip_name')}'")
        if filters.get("time_range"):
            t0, t1 = filters.get("time_range")
            try:
                t0s = datetime.fromtimestamp(t0).strftime("%Y-%m-%d %H:%M")
                t1s = datetime.fromtimestamp(t1).strftime("%Y-%m-%d %H:%M")
                parts.append(f"{t0s}→{t1s}")
            except Exception:
                parts.append("time_range")
        if parts:
            self.filters_label.setText("Фильтры: " + ", ".join(parts))
        else:
            self.filters_label.setText("Фильтры: (нет)")
