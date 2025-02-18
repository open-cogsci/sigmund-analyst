import logging; logging.basicConfig(level=logging.INFO, force=True)
import chardet
from pathlib import Path
from qtpy.QtCore import QFileSystemWatcher
from qtpy.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)

class FileLink:
    """
    A mixin for QPlainTextEdit that links the content of the editor to a
    file on disk. By default, the editor is not linked to any file.

    A QFileSystemWatcher monitors the currently opened file. If the file is
    changed on disk, the user is prompted to possibly reload. (See _on_file_changed.)
    """
    code_editor_file_path = None  # str or None
    code_editor_encoding = None   # str or None
    _file_watcher = None          # QFileSystemWatcher or None

    def open_file(self, path: Path | str, encoding: str = None):
        """
        Reads the content from a file and sets it as the editor content.
        If the file does not exist, a sensible exception is raised.
        If no encoding is specified, tries:
          1) If it's pure ASCII, use 'utf-8'.
          2) Else guess with chardet, or default to 'utf-8' if chardet yields None.
        """
        path = Path(path)  # ensure we have a Path object
        if not path.is_file():
            raise FileNotFoundError(f"No such file: {path}")

        raw_data = path.read_bytes()

        if encoding is None:
            # First see if everything is within ASCII range
            try:
                raw_data.decode("utf-8")
                # If no error -> it's strictly ASCII, so decode as UTF-8
                used_encoding = "utf-8"
            except UnicodeDecodeError:
                # Not pure ASCII; let chardet pick
                detect_result = chardet.detect(raw_data)
                # If detection fails or returns None, default to utf-8
                used_encoding = detect_result["encoding"] or "utf-8"
        else:
            used_encoding = encoding
        logger.info(f'opening file as {used_encoding}')
        # Try reading with the chosen encoding
        with path.open("r", encoding=used_encoding) as f:
            content = f.read()

        # Store the content in the editor
        self.setPlainText(content)

        # Update internal state
        self.code_editor_file_path = str(path)
        self.code_editor_encoding = used_encoding

        # (Re)watch this file
        self._watch_file(path)
        self.modified = False

    def save_file(self):
        """
        Saves the editor content to the file named code_editor_file_path,
        using code_editor_encoding. If no valid path or encoding is available,
        a sensible exception is raised.
        """
        if not self.code_editor_file_path:
            raise ValueError("No file path specified. Use save_file_as() instead or open_file() first.")
        if not self.code_editor_encoding:
            # If no encoding is set, default again to UTF-8
            self.code_editor_encoding = "utf-8"

        path = Path(self.code_editor_file_path)
        with path.open("w", encoding=self.code_editor_encoding) as f:
            f.write(self.toPlainText())
        self.modified = False

    def save_file_as(self, path: Path | str):
        """
        Saves the editor content to file and updates code_editor_file_path.
        If no valid path or encoding is available, a sensible exception is raised.
        """
        path = Path(path)
        if not self.code_editor_encoding:
            # Default to UTF-8 if we have no prior encoding
            self.code_editor_encoding = "utf-8"

        with path.open("w", encoding=self.code_editor_encoding) as f:
            f.write(self.toPlainText())

        # Update internal pointers
        self.code_editor_file_path = str(path)
        self._watch_file(path)
        self.modified = False

    def _watch_file(self, path: Path):
        """Set up the QFileSystemWatcher to watch the newly opened or saved file."""
        # If there's no watcher yet, create one.
        if self._file_watcher is None:
            self._file_watcher = QFileSystemWatcher()
            self._file_watcher.fileChanged.connect(self._on_file_changed)

        # Clear the watcher first (the old file path).
        self._file_watcher.removePaths(self._file_watcher.files())

        # Now watch the new file
        self._file_watcher.addPath(str(path))

    def _on_file_changed(self, changed_path: str):
        """
        Called by QFileSystemWatcher whenever the watched file changes on disk.
        By default, offers the user to reload. If reloaded, calls open_file again.
        """
        # Only respond if it matches the current file
        if changed_path != self.code_editor_file_path:
            return

        # Prompt user to reload
        reply = QMessageBox.warning(
            self, 
            "File changed on disk",
            f"The file:\n{changed_path}\nhas changed on disk.\nReload?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            # Reload file
            logger.info("Reloading file after external change.")
            self.open_file(changed_path, encoding=self.code_editor_encoding)
        else:
            logger.info("User chose not to reload. Re-watching file anyway.")
            # Re-add the file to watcher so we keep listening for future changes
            if self._file_watcher is not None:
                self._file_watcher.addPath(changed_path)
