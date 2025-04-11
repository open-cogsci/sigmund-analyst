import logging
from . import QuickOpenDialog
logger = logging.getLogger(__name__)


class QuickSymbolDialog(QuickOpenDialog):
    def __init__(self, parent, items, jump_to_symbol_callback):
        self.jump_to_symbol_callback = jump_to_symbol_callback
        super().__init__(parent, items, title="Symbols")

    def on_item_selected(self, item_dict: dict):
        self.jump_to_symbol_callback(item_dict)
