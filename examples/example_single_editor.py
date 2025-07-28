import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pyqt_code_editor import watchdog
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget
from pyqt_code_editor.code_editors import create_editor
from pyqt_code_editor.environment_manager import environment_manager


class MainWindow(QWidget):
    def __init__(self, path=None):
        super().__init__()
        self.setWindowTitle("PyQtCodeEditor")
        layout = QVBoxLayout()
        environment_manager.prefix = 'import math'
        self.editor = create_editor(path, parent=self)
        layout.addWidget(self.editor)
        self.setLayout(layout)

    def closeEvent(self, event):
        watchdog.shutdown()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    path = None
    if len(sys.argv) > 1:
        path = sys.argv[1]    
    win = MainWindow(path)
    win.show()
    sys.exit(app.exec_())
