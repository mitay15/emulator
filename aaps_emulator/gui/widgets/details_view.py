from PyQt6 import QtWidgets


class DetailsView(QtWidgets.QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)

    def update_details(self, inp, block):
        gs = inp["glucose_status"]
        prof = inp["profile"]
        meal = inp["meal"]
        autosens = inp["autosens"]
        iob_arr = inp["iob_array"]

        lines = []
        lines.append("=== GlucoseStatus ===")
        lines.append(str(gs))
        lines.append("\n=== Profile ===")
        lines.append(str(prof))
        lines.append("\n=== Meal ===")
        lines.append(str(meal))
        lines.append("\n=== Autosens ===")
        lines.append(str(autosens))
        lines.append("\n=== IOB[0] ===")
        if iob_arr:
            lines.append(str(iob_arr[0]))
        else:
            lines.append("none")

        self.setPlainText("\n".join(lines))
