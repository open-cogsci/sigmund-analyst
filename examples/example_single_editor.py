import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pyqt_code_editor import watchdog
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget, QShortcut
from qtpy.QtGui import QKeySequence
from qtpy.QtCore import Qt
from pyqt_code_editor.code_editors import create_editor
from pyqt_code_editor.environment_manager import environment_manager
from pyqt_code_editor.worker import manager
import logging
logging.basicConfig(level=logging.INFO, force=True)


class MainWindow(QWidget):
    def __init__(self, path=None):
        super().__init__()
        self.setWindowTitle("PyQtCodeEditor")
        layout = QVBoxLayout()
        environment_manager.prefix = 'import math'
        self.editor = create_editor(path, parent=self)
        layout.addWidget(self.editor)
        self.setLayout(layout)

        # Keyboard shortcuts for suspending/resuming workers
        self.suspend_shortcut = QShortcut(QKeySequence("Ctrl+T"), self)
        self.suspend_shortcut.setContext(Qt.ApplicationShortcut)
        self.suspend_shortcut.activated.connect(self.suspend_workers)

        self.resume_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.resume_shortcut.setContext(Qt.ApplicationShortcut)
        self.resume_shortcut.activated.connect(self.resume_workers)

    def suspend_workers(self):
        logging.info("Suspending worker processes")
        manager.suspend()

    def resume_workers(self):
        logging.info("Resuming worker processes")
        manager.resume()

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