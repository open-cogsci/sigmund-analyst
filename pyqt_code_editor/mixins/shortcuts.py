import logging
from qtpy.QtWidgets import QShortcut
from qtpy.QtGui import QTextCursor, QKeySequence
from qtpy.QtCore import Qt, QEvent
from .. import settings
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, force=True)


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
        # We want to remove the trailing or preceding newline, but not both.
        if end < doc_length - 1:
            end += 1
        elif start > 0:
            start -= 1
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.endEditBlock()

    def _current_line_bounds(self, cursor=None):
        """
        Return (start, end) positions of the current line in the document.
        """
        if cursor is None:
            cursor = self.textCursor()
        original_pos = cursor.position()

        cursor.movePosition(QTextCursor.StartOfBlock)
        start = cursor.position()
        cursor.movePosition(QTextCursor.EndOfBlock)
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
        If there is no selection, duplicate the current block. If there is
        a selection, all blocks that are part of the selection should be duplicated.
        The anchor and cursor should be preserved on the lower of the duplicated blocks.
        In other words, it should appear as if the duplication is inserted above.
        """
        cursor = self.textCursor()
        cursor.beginEditBlock()
        
        # 1) Remember original anchor and cursor positions
        original_anchor = cursor.anchor()
        original_position = cursor.position()
        
        # 2) Determine start_pos and end_pos based on anchor / cursor
        start_pos = min(original_anchor, original_position)
        end_pos   = max(original_anchor, original_position)
        
        # 3) Move the cursor to the start of the block that contains start_pos
        cursor.setPosition(start_pos)
        cursor.movePosition(cursor.StartOfBlock)
        start_block_pos = cursor.position()
        
        # 4) Move the cursor to the end of the block containing end_pos (keeping anchor)
        cursor.setPosition(end_pos, cursor.KeepAnchor)
        cursor.movePosition(cursor.EndOfBlock, cursor.KeepAnchor)
        end_block_pos = cursor.position()
        
        # 5) The text that is now selected should be duplicated
        duplication_text = cursor.selectedText()
        # QPlainTextEdit often uses U+2029 for newlines
        duplication_text = duplication_text.replace(u'\u2029', '\n')
        
        # 6) Insert '\n' + duplication_text just after the selection
        #    But first, move cursor to the end of the selected blocks without a selection
        cursor.setPosition(end_block_pos, cursor.MoveAnchor)
        # Now insert a new line plus the duplicated text
        cursor.insertText('\n' + duplication_text)
        
        # Figure out how many characters were inserted
        inserted_length = 1 + len(duplication_text)
        
        # 7) Restore anchor/cursor so that they point to the *new* lines (the lower portion).
        #    According to your docstring, we want the final “visual” anchor/cursor to effectively
        #    be as if the duplication is inserted above, leaving anchor/cursor on the newly inserted lines.        
        cursor.setPosition(original_anchor + inserted_length, cursor.MoveAnchor)
        cursor.setPosition(original_position + inserted_length, cursor.KeepAnchor)
        
        self.setTextCursor(cursor)        
        cursor.endEditBlock()