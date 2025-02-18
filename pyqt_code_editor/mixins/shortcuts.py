import logging; logging.basicConfig(level=logging.INFO, force=True)
from qtpy.QtWidgets import QPlainTextEdit, QShortcut
from qtpy.QtGui import QTextCursor, QKeySequence
from qtpy.QtCore import Qt, QEvent
from .. import settings
logger = logging.getLogger(__name__)


class Shortcuts:
    """
    Mixin that adds common editor shortcuts to a QPlainTextEdit.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Move line up
        self._shortcut_move_line_up = QShortcut(
            QKeySequence(settings.shortcut_move_line_up), self)
        self._shortcut_move_line_up.setContext(Qt.WidgetShortcut)
        self._shortcut_move_line_up.activated.connect(self._move_line_up)

        # Move line down
        self._shortcut_move_line_down = QShortcut(
            QKeySequence(settings.shortcut_move_line_down), self)
        self._shortcut_move_line_down.setContext(Qt.WidgetShortcut)
        self._shortcut_move_line_down.activated.connect(self._move_line_down)

        # Duplicate line
        self._shortcut_duplicate_line = QShortcut(
            QKeySequence(settings.shortcut_duplicate_line), self)
        self._shortcut_duplicate_line.setContext(Qt.WidgetShortcut)
        self._shortcut_duplicate_line.activated.connect(self._duplicate_line)
        
    def eventFilter(self, obj, event):
        """Filters out and handles the 'Cut' shortcut, cross-platform."""
        if obj == self and event.type() == QEvent.KeyPress:
            if event.matches(QKeySequence.Cut):
                if not self.textCursor().hasSelection():
                    self._delete_current_line()
                    return False
        return super().eventFilter(obj, event)
    
    def _delete_current_line(self):
        """
        Removes the current line, preserving undo/redo.
        """
        cursor = self.textCursor()
        start, end = self._current_line_bounds(cursor)
        doc_length = self.document().characterCount()
        
        cursor.beginEditBlock()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        # If not the very last line, remove the trailing newline
        if end < doc_length - 1:
            text = self.toPlainText()
            if end < len(text) and text[end] == '\n':
                cursor.deleteChar()
        cursor.endEditBlock()

    def _current_line_bounds(self, cursor=None):
        """
        Return (start, end) positions of the current line in the document.
        """
        if cursor is None:
            cursor = self.textCursor()
        original_pos = cursor.position()

        cursor.movePosition(QTextCursor.StartOfLine)
        start = cursor.position()
        cursor.movePosition(QTextCursor.EndOfLine)
        end = cursor.position()

        # Restore cursor
        cursor.setPosition(original_pos)
        self.setTextCursor(cursor)
        return start, end

    def _move_lines_impl(self, direction: int):
        """
        Step 1 of the plan:
          - Expand selection to cover the line before and the line after the
            current selection (or the current line if nothing is selected).
          - Ignore 'direction' for now.
        """
        doc = self.document()
        cursor = self.textCursor()
        cursor.beginEditBlock()
    
        anchor = cursor.anchor()
        pos = cursor.position()
    
        # Identify which line is top vs bottom
        anchor_block = doc.findBlock(anchor)
        pos_block = doc.findBlock(pos)
        if anchor_block.firstLineNumber() > pos_block.firstLineNumber():
            anchor_block, pos_block = pos_block, anchor_block
    
        # Expand upward if possible
        prev_block = anchor_block.previous()
        if prev_block.isValid():
            has_preceding_line = True
            anchor_block = prev_block
        else:
            has_preceding_line = False
    
        # Expand downward if possible
        next_block = pos_block.next()
        if next_block.isValid():
            has_following_line = True
            pos_block = next_block
        else:
            has_following_line = False
            
        # Don't move lines up or down if they're already at the start or end
        if not has_preceding_line and direction < 0:
            logger.info('cannot move line up')
            return 
        if not has_following_line and direction > 0:
            logger.info('cannot move line down')
            return 
    
        # Build new selection from start of anchor_block to end of pos_block
        start_pos = anchor_block.position()
        end_pos = pos_block.position() + pos_block.length()
    
        # Set the new selection
        cursor.setPosition(start_pos)
        if end_pos >= doc.characterCount():
            # If the end of the selection is the end of the document, then we
            # need to set it one character sooner, and manually add a newline
            # to the end to compensate for this, but then not pad with a 
            # newline to in turn compensate for the fact that we already padded
            # the selection
            cursor.setPosition(end_pos - 1, QTextCursor.KeepAnchor)
            selection = cursor.selectedText() + '\n'
            insert_padding = ''
        else:
            cursor.setPosition(end_pos, QTextCursor.KeepAnchor)
            selection = cursor.selectedText()
            insert_padding = '\n'
        
        # Get the current selection, and swap the lines according to the 
        # direction in which we're moving. We have special cases for when there
        # is no preceding or following line.
        lines = selection.splitlines()
        if direction < 0:
            anchor -= len(lines[0]) + 1
            pos -= len(lines[0]) + 1
            if has_following_line:
                lines = lines[1:-1] + [lines[0], lines[-1]]
            else:
                lines = lines[1:] + [lines[0]]
        else:
            anchor += len(lines[-1]) + 1
            pos += len(lines[-1]) + 1
            if has_preceding_line:
                lines = [lines[0], lines[-1]] + lines[1:-1]
            else:
                lines = [lines[-1]] + lines[:-1]
        cursor.removeSelectedText()
        cursor.insertText('\n'.join(lines) + insert_padding)
        # Restore the original selection
        cursor.setPosition(anchor)
        cursor.setPosition(pos, QTextCursor.KeepAnchor)
        self.setTextCursor(cursor)        
        cursor.endEditBlock()
        self.refresh()
    
    def _move_line_up(self):
        """Move the currently selected lines (or single line) up by one line."""
        self._move_lines_impl(direction=-1)
    
    def _move_line_down(self):
        """Move the currently selected lines (or single line) down by one line."""
        self._move_lines_impl(direction=1)

    def _duplicate_line(self):
        """
        Duplicate the current line below itself.
        """
        cursor = self.textCursor()
        start, end = self._current_line_bounds(cursor)

        cursor.beginEditBlock()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        line_text = cursor.selectedText()
        
        # Move to the end of line and add newline + copy
        cursor.setPosition(end)
        if end < self.document().characterCount():
            cursor.insertText("\n" + line_text)
        else:
            # If at the end of document, just append
            cursor.insertText("\n" + line_text)
        cursor.endEditBlock()
