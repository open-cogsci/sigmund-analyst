import sys
import logging
from qtpy.QtWidgets import QMainWindow, QApplication
from qtpy.QtCore import Qt, QDir
from pyqt_code_editor.widgets import EditorPanel, ProjectExplorer
from pyqt_code_editor.worker import manager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, root_path=None):
        super().__init__()
        logger.info("MainWindow initialized")
        # If no path is provided, fall back to current dir
        if not root_path:
            root_path = QDir.currentPath()

        self.setWindowTitle("PyQt Code Editor")
        # The editor panel provides splittable editor tabs
        self._editor_panel = EditorPanel()
        self.setCentralWidget(self._editor_panel)
        # Create the project explorer dock
        self._project_explorer = ProjectExplorer(self._editor_panel, root_path=root_path)
        self.addDockWidget(Qt.LeftDockWidgetArea, self._project_explorer)

        
    def closeEvent(self, event):
        manager.stop_all_workers()
        super().closeEvent(event)        


def main():
    logging.basicConfig(level=logging.INFO, force=True)
    logger.info("Starting application")
    app = QApplication(sys.argv)

    # Determine path from command line if provided
    path = None
    if len(sys.argv) > 1:
        path = sys.argv[1]

    window = MainWindow(root_path=path)
    window.resize(1200, 800)
    window.show()
    logger.info("Entering main event loop")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()