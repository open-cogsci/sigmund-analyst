import sys
from pyqt_code_editor.worker import manager
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget
from pyqt_code_editor.code_editors import PythonCodeEditor

SRC = 'pyqt_code_editor/mixins/base.py'


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
        manager.stop_all_workers()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
