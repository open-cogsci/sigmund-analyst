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
    def __init__(self, parent, file_list, open_file_callback):
        self.open_file_callback = open_file_callback
        items = []
        if file_list:
            common_prefix = os.path.commonpath(file_list)
            for full_path in file_list:
                relative_path = os.path.relpath(full_path, common_prefix)
                items.append({
                    "name": relative_path,
                    "full_path": full_path,
                })
        else:
            logger.warning('no files to show')
        super().__init__(parent, items, title="Quick Open File")

    def on_item_selected(self, item_dict: dict):
        """Opens the file at item_dict['full_path'] and closes the dialog."""
        full_path = item_dict.get("full_path", None)
        if full_path:
            self.open_file_callback(full_path)
