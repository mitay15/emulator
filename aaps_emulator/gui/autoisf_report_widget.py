import subprocess
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget

HTML_REPORT = Path("aaps_emulator/tests/autoisf_plotly_report.html")


class PlotBridge(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = None

    @pyqtSlot(int)
    def selectIdx(self, idx: int):
        if self.main_window is not None:
            self.main_window.select_rt(idx)


class AutoISFReportWidget(QWidget):
    report_rebuilt = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.view = QWebEngineView()
        self.refresh_btn = QPushButton("Пересчитать и обновить отчёт")

        layout = QVBoxLayout()
        layout.addWidget(self.refresh_btn)
        layout.addWidget(self.view)
        self.setLayout(layout)

        # WebChannel bridge
        self.channel = QWebChannel()
        self.bridge = PlotBridge()
        self.channel.registerObject("pybridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        self.refresh_btn.clicked.connect(self.rebuild_and_reload)
        self.reload_only()

    def reload_only(self):
        if HTML_REPORT.exists():
            url = QUrl.fromLocalFile(str(HTML_REPORT.resolve()))
            self.view.load(url)

    def rebuild_and_reload(self):
        cmds = [
            ["python", "-m", "aaps_emulator.tools.dump_diffs_and_inputs"],
            ["python", "-m", "aaps_emulator.tools.autoisf_full_report"],
            ["python", "-m", "aaps_emulator.tools.autoisf_plotly_report"],
        ]
        for cmd in cmds:
            subprocess.run(cmd, check=False, shell=False)

        self.reload_only()
        self.report_rebuilt.emit()

    def highlight_idx(self, idx: int):
        js = f"""
        (function() {{
            var plots = document.getElementsByClassName('plotly-graph-div');
            for (let p of plots) {{
                if (!p.data || !p.data.length) continue;
                for (let ci = 0; ci < p.data.length; ci++) {{
                    var trace = p.data[ci];
                    if (!trace.text) continue;
                    for (let pi = 0; pi < trace.text.length; pi++) {{
                        var t = trace.text[pi];
                        if (typeof t === 'string' && t.indexOf('idx={idx}') !== -1) {{
                            Plotly.Fx.hover(p, {{ curveNumber: ci, pointNumber: pi }});
                            return;
                        }}
                    }}
                }}
            }}
        }})();"""
        self.view.page().runJavaScript(js)
