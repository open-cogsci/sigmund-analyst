import sys
import logging
from qtpy.QtWidgets import QMainWindow, QApplication, QShortcut, QMessageBox
from qtpy.QtCore import Qt, QDir
from qtpy.QtGui import QKeySequence
from pyqt_code_editor.widgets import EditorPanel, ProjectExplorer, \
    QuickOpenFileDialog, FindInFiles
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
        self._find_in_files_shortcut = QShortcut(
            QKeySequence(settings.shortcut_find_in_files), self)
        self._find_in_files_shortcut.activated.connect(self._find_in_files)
        
    def _find_in_files(self):
        file_list = []
        for project_explorer in self._project_explorers:
            file_list.extend(project_explorer.list_files())
        find_in_files = FindInFiles(file_list, parent=self)
        find_in_files.open_file_requested.connect(self._open_found_file)
        self.addDockWidget(Qt.RightDockWidgetArea, find_in_files)
        
    def _open_found_file(self, path, line_number):
        self._editor_panel.open_file(path, line_number)

    def _open_project_explorer(self, path):
        project_explorer = ProjectExplorer(self._editor_panel, path, parent=self)
        project_explorer.closed.connect(self._close_project_explorer)
        self.addDockWidget(Qt.LeftDockWidgetArea, project_explorer)
        self._project_explorers.append(project_explorer)
        
    def _close_project_explorer(self, project_explorer):
        self._project_explorers.remove(project_explorer)
        
    def _open_folder(self):
        project_explorer = ProjectExplorer.open_folder(self._editor_panel,
                                                       parent=self)
        if project_explorer is None:
            return
        project_explorer.closed.connect(self._close_project_explorer)
        self.addDockWidget(Qt.LeftDockWidgetArea, project_explorer)
        self._project_explorers.append(project_explorer)        
        
    def closeEvent(self, event):
        # Check if there are unsaved changes, and ask for confirmation if there
        # are
        if self._editor_panel.unsaved_changes():
            message_box = QMessageBox(self)
            message_box.setWindowTitle("Save changes?")
            message_box.setText("Unsaved changes will be permanently lost.")
            message_box.setStandardButtons(
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            message_box.setDefaultButton(QMessageBox.Cancel)
            answer = message_box.exec()
            if answer == QMessageBox.Cancel:
                event.ignore()
                return        
            if answer == QMessageBox.Yes:
                self._editor_panel.save_all_unsaved_changes()
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