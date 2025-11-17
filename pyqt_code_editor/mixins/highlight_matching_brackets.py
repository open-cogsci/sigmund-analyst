import logging
from qtpy.QtCore import QTimer
from qtpy.QtGui import QTextCursor, QColor, QTextCharFormat
from qtpy.QtWidgets import QTextEdit

logger = logging.getLogger(__name__)


class HighlightMatchingBrackets:
    """Highlights matching brackets that match the current cursor position.
    The actual matching is done in the backend.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bracket_request_pending = False
        self._current_bracket_pairs = []

        # Connect to text changes
        self.textChanged.connect(self._on_text_changed)

        # Connect to cursor position changes
        self.cursorPositionChanged.connect(self._on_cursor_changed)

        # Set up debounce timer (500ms)
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._on_debounce_timeout)

    def _on_text_changed(self):
        """Called when text changes - restart debounce timer."""
        # Restart the debounce timer
        self._debounce_timer.stop()
        self._debounce_timer.start(500)

    def _on_debounce_timeout(self):
        """Called after 500ms of no text changes - request bracket update."""
        if not self._bracket_request_pending:
            self._request_matching_brackets()

    def _on_cursor_changed(self):
        """Called when cursor position changes - update highlighting."""
        self._highlight_brackets()

    def _request_matching_brackets(self):
        self._bracket_request_pending = True
        self.send_worker_request(action='matching_brackets',
                                 language=getattr(self, "code_editor_language", "python"),
                                 code=self.toPlainText())

    def _handle_matching_brackets(self, pairs):
        """Pairs is a list of (open_pos, close_pos) positions relative to the
        start of the document.
        """
        self._bracket_request_pending = False
        self._current_bracket_pairs = pairs
        self._highlight_brackets()

    def _highlight_brackets(self):
        """Highlight matching bracket pairs where cursor is on one of the brackets."""
        extra_selections = []
        cursor_pos = self.textCursor().position()
        for open_pos, close_pos in self._current_bracket_pairs:
            # Check if cursor is on either bracket
            if cursor_pos in (open_pos, open_pos + 1,
                              close_pos, close_pos + 1):
                # Highlight opening bracket
                open_selection = self._create_bracket_selection(open_pos)
                if open_selection:
                    extra_selections.append(open_selection)

                # Highlight closing bracket
                close_selection = self._create_bracket_selection(close_pos)
                if close_selection:
                    extra_selections.append(close_selection)

        self.setExtraSelections(extra_selections)

    def _create_bracket_selection(self, pos):
        """Create an extra selection for a single bracket at position."""
        cursor = self.textCursor()
        cursor.setPosition(pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)

        # Create yellow background format
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(255, 255, 0, 50))  # Yellow with some transparency

        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format = fmt

        return selection

    def handle_worker_result(self, action, result):
        super().handle_worker_result(action, result)
        if action == 'matching_brackets':
            logger.info("Handling matching brackets result")
            self._handle_matching_brackets(**result)