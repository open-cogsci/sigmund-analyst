import sys
import logging
from qtpy.QtWidgets import QMainWindow, QApplication, QShortcut
from qtpy.QtCore import Qt, QDir
from qtpy.QtGui import QKeySequence
from pyqt_code_editor.widgets import EditorPanel, ProjectExplorer, \
    QuickOpenFileDialog
from pyqt_code_editor.worker import manager
from pyqt_code_editor import settings

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
        self._project_explorers = []
        self._open_project_explorer(root_path)
                
        # Shortcuts for (quick)opening files and folders
        self._quick_open_shortcut = QShortcut(
            QKeySequence(settings.shortcut_quick_open_file), self)
        self._quick_open_shortcut.activated.connect(self._show_quick_open)        
        self._open_folder_shortcut = QShortcut(
            QKeySequence(settings.shortcut_open_folder), self)
        self._open_folder_shortcut.activated.connect(self._open_folder)        

    def _open_project_explorer(self, path):
        project_explorer = ProjectExplorer(self._editor_panel, path)
        project_explorer.closed.connect(self._close_project_explorer)
        self.addDockWidget(Qt.LeftDockWidgetArea, project_explorer)
        self._project_explorers.append(project_explorer)
        
    def _close_project_explorer(self, project_explorer):
        self._project_explorers.remove(project_explorer)
        
    def _open_folder(self):
        project_explorer = ProjectExplorer.open_folder(self)
        if project_explorer is None:
            return
        project_explorer.closed.connect(self._close_project_explorer)
        self.addDockWidget(Qt.LeftDockWidgetArea, project_explorer)
        self._project_explorers.append(project_explorer)        
        
    def closeEvent(self, event):
        manager.stop_all_workers()
        super().closeEvent(event)

    def _show_quick_open(self):
        """Show a dialog with all files in the project, filtered as user types."""
        file_list = []
        for project_explorer in self._project_explorers:
            file_list.extend(project_explorer.list_files())
        dlg = QuickOpenFileDialog(
            parent=self,
            file_list=file_list,
            open_file_callback=self._editor_panel.open_file,
        )
        dlg.exec_()


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