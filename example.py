import sys
from pathlib import Path
from pyqt_code_editor.worker import manager
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget, QPlainTextEdit
from pyqt_code_editor.mixins import Complete, PythonAutoIndent, \
    PythonAutoPair, HighlightSyntax, Zoom, LineNumber, Comment, \
    SearchReplace, Base, Check, Shortcuts, FileLink


SRC = 'tmp.py'


class PythonCodeEditor(LineNumber, Zoom, PythonAutoPair, Complete,
                       PythonAutoIndent, Comment, SearchReplace, FileLink,
                       HighlightSyntax, Check, Shortcuts, Base,
                       QPlainTextEdit):
    pass


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQtCodeEditor")
        layout = QVBoxLayout()
        self.editor = PythonCodeEditor()
        self.editor.open_file(SRC)
        layout.addWidget(self.editor)
        self.setLayout(layout)

    def closeEvent(self, event):
        # Explicitly stop all workers
        manager.stop_all_workers()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    try:
        sys.exit(app.exec_())
    finally:
        manager.stop_all_workers()
