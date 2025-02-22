import os
import logging
from . import QuickOpenDialog
logger = logging.getLogger(__name__)


class QuickOpenFileDialog(QuickOpenDialog):
    """
    Specialized dialog that handles quickly opening files.
    Collects files in a given root_path, strips common prefix,
    and calls open_file_callback on selection.
    """
    def __init__(self, parent, root_path, open_file_callback):
        self.root_path = os.path.abspath(root_path)
        self.open_file_callback = open_file_callback
        # Gather all files first
        items = self._gather_file_items()
        super().__init__(parent, items, title="Quick Open File")

    def _gather_file_items(self):
        """Recursively gather files from root_path, strip common prefix, build item dicts."""
        all_files = []
        for root, dirs, files in os.walk(self.root_path):
            for f in files:
                full_path = os.path.join(root, f)
                all_files.append(os.path.abspath(full_path))

        # Compute the common path
        if all_files:
            common_prefix = os.path.commonpath(all_files)
        else:
            common_prefix = self.root_path

        items = []
        for full_path in all_files:
            relative_path = os.path.relpath(full_path, common_prefix)
            items.append({
                "name": relative_path,
                "full_path": full_path,
            })
        return items

    def on_item_selected(self, item_dict: dict):
        """Opens the file at item_dict['full_path'] and closes the dialog."""
        full_path = item_dict.get("full_path", None)
        if full_path:
            self.open_file_callback(full_path)
