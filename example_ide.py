"""
TODO: Add a toolbar with the following buttons:
    
- New file
- Open file
- Open folder
---
- Quick select file (from project explorer)
- Quick select symbol (from current file)
----
- Run current file
- Run selected code or cell
- Break kernel
- Restart kernel
----
- Find in files
----
- Split vertically
- Split horizontally
----
- Toggle project explorers
- Toggle Jupyter console
- Toggle workspace explorer
- Toggle Sigmund
"""

import sys
import os
import logging
from qtpy.QtWidgets import QMainWindow, QApplication, QShortcut, QMessageBox, \
    QDockWidget, QToolBar, QAction
from qtpy.QtCore import Qt, QDir
from qtpy.QtGui import QKeySequence
import qtawesome as qta
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
        
        self._setup_toolbar()
    
    def _setup_toolbar(self):
        """Setup the main toolbar with Material Design icons."""
        # Create toolbar
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        
        # FILE OPERATIONS
        # New file button
        new_file_action = QAction(qta.icon('mdi.file-plus'), "New File", self)
        new_file_action.setStatusTip("Create a new file")
        new_file_action.triggered.connect(lambda: self._editor_panel.open_file())
        self.toolbar.addAction(new_file_action)
        
        # Open file button
        open_file_action = QAction(qta.icon('mdi.folder-open'), "Open File", self)
        open_file_action.setStatusTip("Open an existing file")
        open_file_action.triggered.connect(lambda: self._editor_panel.select_and_open_file())
        self.toolbar.addAction(open_file_action)
        
        # Open folder button
        open_folder_action = QAction(qta.icon('mdi.folder-multiple'), "Open Folder", self)
        open_folder_action.setStatusTip("Open a folder as project")
        open_folder_action.triggered.connect(self._open_folder)
        self.toolbar.addAction(open_folder_action)
        
        self.toolbar.addSeparator()
        
        # QUICK ACCESS
        # Quick select file
        quick_file_action = QAction(qta.icon('mdi.file-find'), "Quick Select File", self)
        quick_file_action.setStatusTip("Quickly find and open a file")
        quick_file_action.triggered.connect(self._show_quick_open)
        self.toolbar.addAction(quick_file_action)
        
        # Quick select symbol
        quick_symbol_action = QAction(qta.icon('mdi.code-tags'), "Quick Select Symbol", self)
        quick_symbol_action.setStatusTip("Quickly find a symbol in current file")
        quick_symbol_action.triggered.connect(
            lambda : self._trigger_editor_shortcut('symbol_shortcut'))
        self.toolbar.addAction(quick_symbol_action)
        
        self.toolbar.addSeparator()
        
        # EXECUTION CONTROLS
        # Run current file
        run_file_action = QAction(qta.icon('mdi.play'), "Run File", self)
        run_file_action.setStatusTip("Run the current file")
        run_file_action.triggered.connect(
            lambda : self._trigger_editor_shortcut('execute_file_shortcut'))
        self.toolbar.addAction(run_file_action)
        
        # Run selected code
        run_selection_action = QAction(qta.icon('mdi.play-box-outline'), "Run Cell or Selection", self)
        run_selection_action.setStatusTip("Run the selected cell or lines")
        run_selection_action.triggered.connect(
            lambda : self._trigger_editor_shortcut('execute_code_shortcut'))
        self.toolbar.addAction(run_selection_action)
        
        # Break kernel
        break_kernel_action = QAction(qta.icon('mdi.stop'), "Break Kernel", self)
        break_kernel_action.setStatusTip("Interrupt the kernel")
        break_kernel_action.triggered.connect(lambda: self._jupyter_console.interrupt_current_kernel())
        self.toolbar.addAction(break_kernel_action)
        
        # Restart kernel
        restart_kernel_action = QAction(qta.icon('mdi.restart'), "Restart Kernel", self)
        restart_kernel_action.setStatusTip("Restart the kernel")
        restart_kernel_action.triggered.connect(lambda: self._jupyter_console.restart_current_kernel())
        self.toolbar.addAction(restart_kernel_action)
        
        self.toolbar.addSeparator()
        
        # FIND IN FILES
        find_in_files_action = QAction(qta.icon('mdi.file-search'), "Find in Files", self)
        find_in_files_action.setStatusTip("Search across multiple files")
        find_in_files_action.triggered.connect(self._find_in_files)
        self.toolbar.addAction(find_in_files_action)
        
        self.toolbar.addSeparator()
        
        # SPLIT VIEWS
        # Oddly, the icons need to be reversed because the horizontal icon 
        # depicts a vertical split and vice versa
        split_vert_action = QAction(qta.icon('mdi.arrow-split-horizontal'), "Split Vertically", self)
        split_vert_action.setStatusTip("Split the editor vertically")
        split_vert_action.triggered.connect(lambda: self._editor_panel.split(Qt.Vertical))
        self.toolbar.addAction(split_vert_action)
        
        split_horz_action = QAction(qta.icon('mdi.arrow-split-vertical'), "Split Horizontally", self)
        split_horz_action.setStatusTip("Split the editor horizontally")
        split_horz_action.triggered.connect(lambda: self._editor_panel.split(Qt.Horizontal))
        self.toolbar.addAction(split_horz_action)
        
        self.toolbar.addSeparator()
        
        # TOGGLE PANELS
        toggle_project_action = QAction(qta.icon('mdi.folder-outline'), "Toggle Project Explorer", self)
        toggle_project_action.setStatusTip("Show/hide project explorers")
        toggle_project_action.triggered.connect(self._toggle_project_explorers)
        self.toolbar.addAction(toggle_project_action)
        
        toggle_jupyter_action = QAction(qta.icon('mdi.console'), "Toggle Jupyter Console", self)
        toggle_jupyter_action.setStatusTip("Show/hide Jupyter console")
        toggle_jupyter_action.triggered.connect(lambda: self._toggle_dock_widget(self._jupyter_console))
        self.toolbar.addAction(toggle_jupyter_action)
        
        toggle_workspace_action = QAction(qta.icon('mdi.view-list'), "Toggle Workspace Explorer", self)
        toggle_workspace_action.setStatusTip("Show/hide workspace explorer")
        toggle_workspace_action.triggered.connect(lambda: self._toggle_dock_widget(self._workspace_explorer))
        self.toolbar.addAction(toggle_workspace_action)
        
        toggle_sigmund_action = QAction(qta.icon('mdi.brain'), "Toggle Sigmund", self)
        toggle_sigmund_action.setStatusTip("Show/hide Sigmund")
        toggle_sigmund_action.triggered.connect(lambda: self._toggle_dock_widget(self._sigmund))
        self.toolbar.addAction(toggle_sigmund_action)
        
    def _trigger_editor_shortcut(self, shortcut):
        editor = self._editor_panel.active_editor()
        if editor is not None and hasattr(editor, shortcut):
            getattr(editor, shortcut).activated.emit()
    
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