from qtpy.QtCore import Qt
from qtpy.QtGui import QKeyEvent, QTextCursor
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class SmartBackspaceDelete:
    """
    This is meant to be used as a mixin for QPlainTextEdit to enhance the
    functionality of backspace and delete in a code editor. It re-implements
    keyPressEvent(), supporting the following behavior:

    1) Backspace anywhere in the whitespace at the end of a line:
       - Full right-trim of the whitespace for that line (including whitespace
         before the cursor).
       - Place the cursor at the end of the trimmed line.
    2) Backspace at the very start of a line:
       - Delete the preceding newline and trailing whitespace on the previous
         line (up to the first non-whitespace or newline).
       - Place the cursor at the end of the trimmed preceding line.
    3) Delete anywhere in the whitespace at the end of a line (except the
       very last position):
       - Right-trim from the cursor position onward.
       - The cursor does not move, so it can remain at the same block/column
         index once the whitespace is removed.
    4) Delete at the very end of a line:
       - Delete the next newline and the leading whitespace on the next line
         up to the first non-whitespace or newline.
       - Keep the cursor where it was, effectively pulling up the next line.
    """

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Handle the specific 'backspace anywhere in the whitespace at the
        end of a line' logic. If not applicable, fall back to default behavior.
        """
        c = self.textCursor()
        # We don't handle special cases if there is a selection
        if c.hasSelection():
            super().keyPressEvent(event)
            return
        key = event.key()
        block = c.block()
        pos = c.positionInBlock()
        text = block.text()
        block_length = len(text)
        stripped_block_length = len(text.rstrip())
        in_trailing_whitespace = text[pos:].isspace()
        has_trailing_whitespace = block_length > stripped_block_length
        at_block_end = pos == block_length
        # We don't do anything with empty lines unless we're at the start of the
        # block
        if text.isspace() and pos > 0:
            super().keyPressEvent(event)
            return
        # If we're at the very start of the line, then we're also eating up the
        # trailing whitespace of the previous line. We do this by first moving to
        # the end of the previous line, then handling this case recursively, and
        # finally deleting the newline.
        if key == Qt.Key_Backspace and pos == 0 and block.previous().isValid():
            logger.info('moving to end of previous block')
            c.movePosition(QTextCursor.PreviousBlock, QTextCursor.MoveAnchor)
            c.movePosition(QTextCursor.EndOfBlock, QTextCursor.MoveAnchor)
            self.setTextCursor(c)
            # We only delete trailing whitespace if the previous line has 
            # trailing whitespace
            prev_text = c.block().text()
            if prev_text.rstrip() != prev_text:
                logger.info('removing trailing whitespace from previous block')
                self.keyPressEvent(event)
            else:
                logger.info('previous block doesn\'t have trailing whitespace')
            logger.info('removing neweline')
            c = self.textCursor()
            c.movePosition(QTextCursor.NextBlock, QTextCursor.KeepAnchor)
            c.removeSelectedText()
            self.setTextCursor(c)
            return
        # If we're in the whitespace at the end of the block, we delete all 
        # trailing whitespace.
        if key == Qt.Key_Backspace and has_trailing_whitespace and \
                (in_trailing_whitespace or at_block_end):
            n_trim = block_length - stripped_block_length
            logger.info(f'trimming {n_trim} whitespace from end of block')
            c.movePosition(QTextCursor.EndOfBlock)
            c.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, n_trim)
            c.removeSelectedText()
            self.setTextCursor(c)
            event.accept()
            return
        # If we're in the whitespace at the end of the block, we delete all 
        # trailing whitespace that follows the cursor.
        if key == Qt.Key_Delete and in_trailing_whitespace:
            n_trim = block_length - pos
            logger.info(f'trimming {n_trim} whitespace from end of block')
            c.movePosition(QTextCursor.EndOfBlock)
            c.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, n_trim)
            c.removeSelectedText()
            self.setTextCursor(c)
            event.accept()
            return
        # If we're at the end of a line, then delete removes the next line break
        # and the leading whitespace on the next line. We do this by first moving
        # to the next block, calculating how much leading whitespace there is,
        # then getting a fresh cursor and removing this leading whitespace plus
        # one character for the newline.
        if key == Qt.Key_Delete and at_block_end and block.next().isValid():
            c.movePosition(QTextCursor.NextBlock, QTextCursor.MoveAnchor)
            next_text = c.block().text()
            n_trim = len(next_text) - len(next_text.lstrip()) + 1
            c = self.textCursor()
            c.movePosition(
                QTextCursor.NextCharacter, QTextCursor.KeepAnchor, n_trim)
            c.removeSelectedText()
            self.setTextCursor(c)
            event.accept()
            return                    
        # In any situation, fall back
        super().keyPressEvent(event)