import os
import shutil
import logging
from qtpy.QtWidgets import (
    QDockWidget,
    QTreeView,
    QFileDialog,
    QMenu,
    QMessageBox,
    QShortcut,    
)
from qtpy.QtCore import Qt, QDir, QModelIndex
from qtpy.QtWidgets import QFileSystemModel
from qtpy.QtGui import QKeySequence
from . import QuickOpenFileDialog
from .. import settings

logger = logging.getLogger(__name__)


class ProjectExplorer(QDockWidget):

    def __init__(self, editor_panel, root_path=None, parent=None):
        super().__init__("Project Explorer", parent)
        self._editor_panel = editor_panel

        # Our local "clipboard" for cut/copy/paste
        self._clipboard_operation = None  # 'cut' or 'copy'
        self._clipboard_source_path = None

        # Main widget inside the dock
        self._tree_view = QTreeView(self)
        self._model = QFileSystemModel(self._tree_view)
        self._model.setRootPath(root_path or QDir.currentPath())
        # Optionally hide filters, e.g.:
        # self._model.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs | QDir.Files)
        self._tree_view.setModel(self._model)

        # Controls columns
        self.set_single_column_view(True)

        # If a root_path was specified, set that as the visible root:
        if root_path:
            root_idx = self._model.index(root_path)
            if root_idx.isValid():
                self._tree_view.setRootIndex(root_idx)

        # Configure QTreeView
        self._tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree_view.customContextMenuRequested.connect(self._show_context_menu)
        self._tree_view.doubleClicked.connect(self._on_double_click)
        self.setWidget(self._tree_view)

        # Shortcut for quick-open
        self._quick_open_shortcut = QShortcut(QKeySequence(settings.shortcut_quick_open_file), self)
        self._quick_open_shortcut.activated.connect(self._show_quick_open)

    def set_single_column_view(self, single_column=True):
        """If single_column=True, show only the file name column with no header."""
        if single_column:
            # Hide columns 1,2,3 (Size, Type, Date Modified) and hide the header
            self._tree_view.setHeaderHidden(True)
            for col in range(1, 4):
                self._tree_view.setColumnHidden(col, True)
        else:
            # Show all columns and show the header
            self._tree_view.setHeaderHidden(False)
            for col in range(1, 4):
                self._tree_view.setColumnHidden(col, False)
                
    def _show_quick_open(self):
        """Show a dialog with all files in the project, filtered as user types."""
        root_path = self._model.rootPath()
        dlg = QuickOpenFileDialog(
            parent=self,
            root_path=root_path,
            open_file_callback=self._editor_panel.open_file,
        )
        dlg.exec_()

    def _on_double_click(self, index: QModelIndex):
        """Open file on double-click if it's not a directory."""
        path = self._model.filePath(index)
        if os.path.isfile(path):
            logger.info(f"Double-click opening file: {path}")
            self._editor_panel.open_file(path)
        else:
            logger.info(f"Double-clicked on directory: {path}")

    def _show_context_menu(self, pos):
        """Build and show a context menu on right-click."""
        index = self._tree_view.indexAt(pos)
        if not index.isValid():
            return  # clicked on empty area

        menu = QMenu(self)

        path = self._model.filePath(index)
        is_file = os.path.isfile(path)

        open_action = menu.addAction("Open")
        open_action.setEnabled(is_file)

        new_file_action = menu.addAction("New File…")
        rename_action = menu.addAction("Rename…")
        delete_action = menu.addAction("Delete")

        menu.addSeparator()
        cut_action = menu.addAction("Cut")
        copy_action = menu.addAction("Copy")
        paste_action = menu.addAction("Paste")
        paste_action.setEnabled(self._clipboard_source_path is not None)

        chosen_action = menu.exec_(self._tree_view.mapToGlobal(pos))
        if chosen_action == open_action:
            self._editor_panel.open_file(path)
        elif chosen_action == new_file_action:
            self._create_new_file(os.path.dirname(path) if is_file else path)
        elif chosen_action == rename_action:
            self._rename_file_or_folder(path)
        elif chosen_action == delete_action:
            self._delete_file_or_folder(path)
        elif chosen_action == cut_action:
            self._clipboard_operation = 'cut'
            self._clipboard_source_path = path
        elif chosen_action == copy_action:
            self._clipboard_operation = 'copy'
            self._clipboard_source_path = path
        elif chosen_action == paste_action:
            self._paste_file_or_folder(path)

    def _create_new_file(self, folder):
        """Create a new file in the specified folder."""
        if not os.path.isdir(folder):
            return
        # Ask user for file name
        file_name, ok = QFileDialog.getSaveFileName(self, "New File", folder)
        if not ok or not file_name:
            return
        try:
            with open(file_name, 'w', encoding='utf8') as f:
                f.write("")
            logger.info(f"Created file: {file_name}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create file:\n{str(e)}")

    def _rename_file_or_folder(self, path):
        """Rename a file or folder via an input dialog, then rename in filesystem."""
        base_dir = os.path.dirname(path)
        old_name = os.path.basename(path)
        new_name, ok = QFileDialog.getSaveFileName(self, "Rename", os.path.join(base_dir, old_name))
        if not ok or not new_name:
            return
        try:
            os.rename(path, new_name)
            logger.info(f"Renamed {path} to {new_name}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to rename:\n{str(e)}")

    def _delete_file_or_folder(self, path):
        """Delete a file or entire folder."""
        reply = QMessageBox.question(self, "Delete", f"Delete '{path}'?", 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return
        try:
            if os.path.isfile(path):
                os.remove(path)
            else:
                shutil.rmtree(path)
            logger.info(f"Deleted: {path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to delete:\n{str(e)}")

    def _paste_file_or_folder(self, target_path):
        """Paste files/folders from our local 'clipboard_operation' into target_path."""
        if not self._clipboard_operation or not self._clipboard_source_path:
            return
        # If target_path is a file, use its directory as the actual destination.
        if os.path.isfile(target_path):
            target_path = os.path.dirname(target_path)
        if not os.path.isdir(target_path):
            QMessageBox.warning(self, "Error", "Target is not a valid folder.")
            return

        src = self._clipboard_source_path
        dst = os.path.join(target_path, os.path.basename(src))
        try:
            if self._clipboard_operation == 'copy':
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            elif self._clipboard_operation == 'cut':
                shutil.move(src, dst)
            logger.info(f"{self._clipboard_operation.title()} '{src}' to '{dst}'")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to {self._clipboard_operation}:\n{str(e)}")

        # Clear our local clipboard
        self._clipboard_operation = None
        self._clipboard_source_path = None
