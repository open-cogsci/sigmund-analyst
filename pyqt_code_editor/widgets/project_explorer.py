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
    QInputDialog
)
from qtpy.QtCore import Qt, QDir, QModelIndex
from qtpy.QtWidgets import QFileSystemModel
from qtpy.QtGui import QKeySequence
from . import QuickOpenFileDialog
from .. import settings

logger = logging.getLogger(__name__)

class LazyQFileSystemModel(QFileSystemModel):
    """
    A QFileSystemModel that only fetches children for 'expanded' paths.
    This prevents eagerly creating inotify watchers for large, collapsed directories.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded_paths = set()

    def setRootPath(self, root):
        idx = super().setRootPath(root)
        # Ensure the root path is always considered expanded
        if root:
            self._expanded_paths.add(root)
            # Force a fetch so we see the root directory contents
            if idx.isValid() and super().canFetchMore(idx):
                super().fetchMore(idx)
        return idx

    def notify_path_expanded(self, path):
        self._expanded_paths.add(path)
        # Manually trigger fetch
        index = self.index(path)
        if super().canFetchMore(index):
            super().fetchMore(index)

    def notify_path_collapsed(self, path):
        if path in self._expanded_paths:
            self._expanded_paths.remove(path)

    def canFetchMore(self, index):
        if not index.isValid():
            return super().canFetchMore(index)
        path = self.filePath(index)
        # Only allow fetch if path is in expanded set
        if path in self._expanded_paths:
            return super().canFetchMore(index)
        return False

    def fetchMore(self, index):
        if not index.isValid():
            return super().fetchMore(index)
        path = self.filePath(index)
        # Only do the actual fetch for expanded paths
        if path in self._expanded_paths:
            return super().fetchMore(index)


class ProjectExplorer(QDockWidget):

    def __init__(self, editor_panel, root_path=None, parent=None):
        super().__init__("Project Explorer", parent)
        self._editor_panel = editor_panel

        # Our local "clipboard" for cut/copy/paste
        self._clipboard_operation = None  # 'cut' or 'copy'
        self._clipboard_source_path = None

        # Main widget inside the dock
        self._tree_view = QTreeView(self)

        # Use our custom LazyQFileSystemModel
        self._model = LazyQFileSystemModel(self._tree_view)
        display_root = root_path or QDir.currentPath()
        self._model.setRootPath(display_root)

        self._tree_view.setModel(self._model)

        # Connect expanded/collapsed signals to limit watchers
        self._tree_view.expanded.connect(self._on_expanded)
        self._tree_view.collapsed.connect(self._on_collapsed)

        # Optional: Hide columns other than the file name
        self.set_single_column_view(True)

        # Make the root folder visible and expanded
        root_idx = self._model.index(display_root)
        if root_idx.isValid():
            self._tree_view.setRootIndex(root_idx)
            # Also expand the root so it behaves like an “expanded” folder
            self._tree_view.expand(root_idx)

        # Configure QTreeView
        self._tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree_view.customContextMenuRequested.connect(self._show_context_menu)
        self._tree_view.doubleClicked.connect(self._on_double_click)
        self.setWidget(self._tree_view)

        # Shortcut for quick-open
        self._quick_open_shortcut = QShortcut(QKeySequence(settings.shortcut_quick_open_file), self)
        self._quick_open_shortcut.activated.connect(self._show_quick_open)

    def _on_expanded(self, index: QModelIndex):
        # Notify the model that this path is expanded
        path = self._model.filePath(index)
        self._model.notify_path_expanded(path)

    def _on_collapsed(self, index: QModelIndex):
        # Notify the model that this path is collapsed
        path = self._model.filePath(index)
        self._model.notify_path_collapsed(path)

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
        menu = QMenu(self)

        if not index.isValid():
            # Clicked on empty space:
            # We want "New File…" and "New Folder…" relative to the root folder
            new_file_action = menu.addAction("New File…")
            new_folder_action = menu.addAction("New Folder…")
            chosen_action = menu.exec_(self._tree_view.mapToGlobal(pos))

            if chosen_action == new_file_action:
                # Use model root path
                root_path = self._model.rootPath()
                if os.path.isdir(root_path):
                    self._create_new_file(root_path)
            elif chosen_action == new_folder_action:
                root_path = self._model.rootPath()
                if os.path.isdir(root_path):
                    self._create_new_folder(root_path)

        else:
            path = self._model.filePath(index)
            is_file = os.path.isfile(path)

            if is_file:
                # Right-clicked on a file
                open_action = menu.addAction("Open")
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

            else:
                # Right-clicked on a folder
                open_action = menu.addAction("Open")
                new_file_action = menu.addAction("New File…")
                new_folder_action = menu.addAction("New Folder…")
                rename_action = menu.addAction("Rename…")
                delete_action = menu.addAction("Delete")

                menu.addSeparator()
                cut_action = menu.addAction("Cut")
                copy_action = menu.addAction("Copy")
                paste_action = menu.addAction("Paste")
                paste_action.setEnabled(self._clipboard_source_path is not None)

                chosen_action = menu.exec_(self._tree_view.mapToGlobal(pos))
                if chosen_action == open_action:
                    # "Open" could mean different behaviors, e.g., expand folder or something else
                    # For now, let's expand the folder:
                    idx = self._tree_view.indexAt(pos)
                    if idx.isValid() and not self._tree_view.isExpanded(idx):
                        self._tree_view.expand(idx)
                elif chosen_action == new_file_action:
                    self._create_new_file(path)
                elif chosen_action == new_folder_action:
                    self._create_new_folder(path)
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
        file_name, ok = QFileDialog.getSaveFileName(self, "New File", folder)
        if not ok or not file_name:
            return
        try:
            with open(file_name, 'w', encoding='utf8') as f:
                f.write("")
            logger.info(f"Created file: {file_name}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create file:\n{str(e)}")

    def _create_new_folder(self, parent_folder):
        """Creates a new subfolder inside 'parent_folder'."""
        if not os.path.isdir(parent_folder):
            return
        folder_name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not folder_name:
            return

        new_path = os.path.join(parent_folder, folder_name)
        try:
            os.mkdir(new_path)
            logger.info(f"Created folder: {new_path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create folder:\n{str(e)}")

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
        reply = QMessageBox.question(
            self, "Delete",
            f"Delete '{path}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
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

        self._clipboard_operation = None
        self._clipboard_source_path = None