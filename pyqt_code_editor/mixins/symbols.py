import logging
from qtpy.QtGui import QShortcut
from qtpy.QtCore import Qt, Signal
from .. import settings
from ..widgets import QuickSymbolDialog
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

    
class Symbols:
    """
    A mixin for QPlainTextEdit that provides all symbols (functions, classes, etc.)
    for the current file.
    """
    symbols_available = Signal(list)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("Initializing symbols")
        self.symbol_shortcut = QShortcut(settings.shortcut_symbols, self)
        self.symbol_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.symbol_shortcut.activated.connect(self.request_symbols)                
    
    def request_symbols(self):
        logger.info("Requesting symbols")
        code = self.toPlainText()
        self.send_worker_request(action='symbols', code=code,
                                 path=self.code_editor_file_path,
                                 language=self.code_editor_language)

    def handle_worker_result(self, action, result):
        """Check for completion or calltip results from the external worker."""
        super().handle_worker_result(action, result)
        if action != 'symbols' or not result.get('symbols', False):
            return
        QuickSymbolDialog(self, result['symbols'], self.jump_to_symbol).exec()
        
    def jump_to_symbol(self, symbol):
        block_nr = symbol['line'] - 1
        cursor = self.textCursor()
        # Jump to block number
        cursor.setPosition(self.document().findBlockByNumber(block_nr).position())
        self.setTextCursor(cursor)
        self.centerCursor()
        self.ensureCursorVisible()
