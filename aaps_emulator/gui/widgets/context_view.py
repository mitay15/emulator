from PyQt6 import QtWidgets


class ContextView(QtWidgets.QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.NoWrap)

    def update_context(self, block):
        text = "\n".join(block["context"]) + "\n\n" + block["rt"]
        self.setPlainText(text)
