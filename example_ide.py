import sys
import os
import logging
from qtpy.QtWidgets import QMainWindow, QApplication, QShortcut, QMessageBox, QDockWidget
from qtpy.QtCore import Qt, QDir
from qtpy.QtGui import QKeySequence
from pyqt_code_editor.widgets import QuickOpenFileDialog
from pyqt_code_editor.components.editor_panel import EditorPanel
from pyqt_code_editor.components.project_explorer import ProjectExplorer
from pyqt_code_editor.components.find_in_files import FindInFiles
from pyqt_code_editor.components.jupyter_console import JupyterConsole
from pyqt_code_editor.components.workspace_explorer import WorkspaceExplorer
from pyqt_code_editor.components.sigmund import Sigmund
from pyqt_code_editor import settings, watchdog
from pyqt_code_editor.signal_router import signal_router

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, root_path=None):
        super().__init__()
        logger.info("MainWindow initialized")
        # If no path is provided, fall back to current dir
        if not root_path:
            root_path = QDir.currentPath()

        self.setWindowTitle("Sigmund Analyst")
        # The editor panel provides splittable editor tabs
        self._editor_panel = EditorPanel()
        self.setCentralWidget(self._editor_panel)
        self._project_explorers = []
        # Track if project explorers are hidden as a group
        self._project_explorers_hidden = False
        self._open_project_explorer(root_path)        
        
        # Set up the workspace explorer
        self._workspace_explorer = WorkspaceExplorer(parent=self)
        self.addDockWidget(Qt.RightDockWidgetArea, self._workspace_explorer)
        self._setup_dock_widget(self._workspace_explorer, "Workspace Explorer")
        
        # Set up the jupyter console
        self._jupyter_console = JupyterConsole(parent=self)
        self._jupyter_console.workspace_updated.connect(
            self._workspace_explorer.update)
        self.addDockWidget(Qt.BottomDockWidgetArea, self._jupyter_console)
        self._setup_dock_widget(self._jupyter_console, "Jupyter Console")
        
        # Set up Sigmund
        self._sigmund = Sigmund(parent=self, editor_panel=self._editor_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self._sigmund)
        self._setup_dock_widget(self._sigmund, "Sigmund")
                
        # Shortcuts
        self._quick_open_shortcut = QShortcut(
            QKeySequence(settings.shortcut_quick_open_file), self)
        self._quick_open_shortcut.activated.connect(self._show_quick_open)        
        self._open_folder_shortcut = QShortcut(
            QKeySequence(settings.shortcut_open_folder), self)
        self._open_folder_shortcut.activated.connect(self._open_folder)        
        self._find_in_files_shortcut = QShortcut(
            QKeySequence(settings.shortcut_find_in_files), self)
        self._find_in_files_shortcut.activated.connect(self._find_in_files)
        
        # Add dock widget visibility toggle shortcuts
        self._workspace_toggle_shortcut = QShortcut(
            QKeySequence(settings.shortcut_toggle_workspace_explorer), self)
        self._workspace_toggle_shortcut.activated.connect(
            lambda: self._toggle_dock_widget(self._workspace_explorer))
            
        self._jupyter_toggle_shortcut = QShortcut(
            QKeySequence(settings.shortcut_toggle_jupyter_console), self)
        self._jupyter_toggle_shortcut.activated.connect(
            lambda: self._toggle_dock_widget(self._jupyter_console))
            
        self._sigmund_toggle_shortcut = QShortcut(
            QKeySequence(settings.shortcut_toggle_sigmund), self)
        self._sigmund_toggle_shortcut.activated.connect(
            lambda: self._toggle_dock_widget(self._sigmund))
            
        # Add project explorer group toggle shortcut
        self._project_toggle_shortcut = QShortcut(
            QKeySequence(settings.shortcut_toggle_project_explorers), self)
        self._project_toggle_shortcut.activated.connect(
            self._toggle_project_explorers)
        
        # Connect to dynamically created signals
        signal_router.connect_to_signal("execute_code", self._execute_code)
        signal_router.connect_to_signal("execute_file", self._execute_file)
    
    def _setup_dock_widget(self, dock_widget, name):
        """Configures dock widget to hide on close instead of actually closing."""
        if isinstance(dock_widget, QDockWidget):
            # Override close behavior
            dock_widget.closeEvent = lambda event: self._handle_dock_close(event, dock_widget)
        else:
            # If the dock widget is a custom class with a close_requested signal
            if hasattr(dock_widget, 'close_requested'):
                dock_widget.close_requested.connect(
                    lambda: self._toggle_dock_widget(dock_widget, show=False))
    
    def _handle_dock_close(self, event, dock_widget):
        """Handles close events for dock widgets by hiding them instead."""
        event.ignore()  # Prevent the actual close
        dock_widget.hide()
        
    def _toggle_dock_widget(self, dock_widget, show=None):
        """Toggle the visibility of a dock widget."""
        if show is None:
            # Toggle visibility
            dock_widget.setVisible(not dock_widget.isVisible())
        else:
            # Set to specific state
            dock_widget.setVisible(show)
    
    def _toggle_project_explorers(self):
        """Toggle visibility of all project explorers as a group."""
        # Toggle the hidden state
        self._project_explorers_hidden = not self._project_explorers_hidden
        
        # Apply the visibility to all project explorers
        for explorer in self._project_explorers:
            explorer.setVisible(not self._project_explorers_hidden)
            
    def _normalize_line_breaks(self, text):
        """Convert paragraph separators (U+2029) to standard newlines."""
        return text.replace('\u2029', '\n')
        
    def _execute_code(self, code):
        editor = self._editor_panel.active_editor()
        if editor is not None and editor.code_editor_file_path is not None:
            self._jupyter_console.change_directory(
                os.path.dirname(editor.code_editor_file_path))
        self._jupyter_console.execute_code(code)
        
    def _execute_file(self, path):
        self._jupyter_console.execute_file(path)
        
    def _find_in_files(self):
        file_list = []
        for project_explorer in self._project_explorers:
            file_list.extend(project_explorer.list_files())
        editor = self._editor_panel.active_editor()
        if editor is not None:
            selected_text = editor.textCursor().selectedText()
            # Normalize line breaks
            selected_text = self._normalize_line_breaks(selected_text)
            lines = selected_text.splitlines()
            if len(lines) == 1:
                needle = lines[0].strip()
            else:
                needle = None
        else:
            needle = None
        find_in_files = FindInFiles(file_list, parent=self, needle=needle)
        find_in_files.open_file_requested.connect(self._open_found_file)
        self.addDockWidget(Qt.RightDockWidgetArea, find_in_files)
        
    def _open_found_file(self, path, line_number):
        self._editor_panel.open_file(path, line_number)

    def _open_project_explorer(self, path):
        project_explorer = ProjectExplorer(self._editor_panel, path, parent=self)
        project_explorer.closed.connect(self._close_project_explorer)
        self.addDockWidget(Qt.LeftDockWidgetArea, project_explorer)
        self._project_explorers.append(project_explorer)
        
        # If project explorers were hidden as a group, make them all visible again
        if self._project_explorers_hidden:
            self._project_explorers_hidden = False
            for explorer in self._project_explorers:
                explorer.setVisible(True)
        
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
        
        # If project explorers were hidden as a group, make them all visible again
        if self._project_explorers_hidden:
            self._project_explorers_hidden = False
            for explorer in self._project_explorers:
                explorer.setVisible(True)
        
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
        watchdog.shutdown()
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