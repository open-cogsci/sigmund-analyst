import sys
from pyqt_code_editor.worker import manager
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget
from pyqt_code_editor.code_editors import create_editor


class MainWindow(QWidget):
    def __init__(self, path=None):
        super().__init__()
        self.setWindowTitle("PyQtCodeEditor")
        layout = QVBoxLayout()
        self.editor = create_editor(path)
        layout.addWidget(self.editor)
        self.setLayout(layout)

    def closeEvent(self, event):
        manager.stop_all_workers()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Determine path from command line if provided
    path = None
    if len(sys.argv) > 1:
        path = sys.argv[1]    
    win = MainWindow(path)
    win.show()
    sys.exit(app.exec_())
