from qtpy.QtCore import Qt
from qtpy.QtGui import QTextCursor
from .. import settings
from ..utils.languages import python as python_utils
import logging
logging.basicConfig(level=logging.INFO, force=True)


class PythonAutoIndent:
    """
    A mixin class to provide Python-specific auto-indentation,
    suitable for mixing into a QPlainTextEdit subclass.

    This version includes more "smart" indentation heuristics:
      1. Increase indentation for lines ending in ':' (block start).
      2. Increase indentation for an open bracket '([{', if it has no closing match
         on the same line (simple heuristic).
      3. Attempt to align arguments if we detect a function call or definition
         continuing onto the next line.
      4. Dedent if the new line starts with keywords like 'elif' or 'else'.
      5. Basic bracket matching to align closing brackets with the line holding
         the corresponding open bracket (though for brevity we show a simple approach).
    """

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        logging.info("keyPressEvent: key=%s, modifiers=%s", key, modifiers)

        # Check for Tab/Shift+Tab indentation
        if key == Qt.Key_Tab and modifiers == Qt.NoModifier:
            logging.info("Tab pressed, indent code")
            self.indent_code()
            return
        elif (key == Qt.Key_Tab and modifiers == Qt.ShiftModifier) or key == Qt.Key_Backtab:
            logging.info("Shift+Tab pressed, dedent code")
            self.dedent_code()
            return

        # Handle backspace in leading indentation
        if key == Qt.Key_Backspace and modifiers == Qt.NoModifier:
            if self._handle_backspace():
                return

        # Handle delete in leading indentation
        if key == Qt.Key_Delete and modifiers == Qt.NoModifier:
            if self._handle_delete():
                return

        # Check for Enter/Return
        if key in (Qt.Key_Enter, Qt.Key_Return):
            logging.info("Enter/Return pressed")
            cursor = self.textCursor()
            cursor.beginEditBlock()
    
            # Use QTextCursor to get text up to cursor position
            # This handles UTF-16 encoding correctly
            temp_cursor = self.textCursor()
            temp_cursor.movePosition(QTextCursor.Start)
            temp_cursor.setPosition(cursor.position(), QTextCursor.KeepAnchor)
            code = temp_cursor.selectedText().replace('\u2029', '\n')
    
            new_indent = python_utils.python_auto_indent(code)
            # Insert the computed indentation
            super().keyPressEvent(event)
            if new_indent > 0:
                logging.info("Inserting %d spaces of indentation", new_indent)
                self._insert_indentation(new_indent)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
            return
        # Otherwise, default behavior
        super().keyPressEvent(event)

    def _handle_backspace(self):
        """
        If the cursor is in leading indentation, remove a 'tab chunk'
        of spaces (settings.tab_width), otherwise let normal backspace happen.
        Returns True if we handled it, False if not.
        """
        cursor = self.textCursor()
        if not cursor.hasSelection():
            block_text = cursor.block().text()
            pos_in_block = cursor.positionInBlock()
            leading_spaces = len(block_text) - len(block_text.lstrip(' '))

            # Only if we're in the leading whitespace region:
            if pos_in_block > 0 and pos_in_block <= leading_spaces:
                # Figure out how many spaces to remove
                remainder = pos_in_block % settings.tab_width
                if remainder == 0:
                    remainder = settings.tab_width

                remove_count = min(remainder, pos_in_block)
                logging.info("Backspace in leading indentation, removing %d spaces", remove_count)

                # Delete the chunk of spaces
                for _ in range(remove_count):
                    cursor.deletePreviousChar()
                return True
        return False

    def _handle_delete(self):
        """
        If the cursor is in leading indentation, remove a 'tab chunk'
        of spaces (settings.tab_width) going forward, otherwise let normal delete happen.
        Returns True if we handled it, False if not.
        """
        cursor = self.textCursor()
        if not cursor.hasSelection():
            block_text = cursor.block().text()
            pos_in_block = cursor.positionInBlock()
            leading_spaces = len(block_text) - len(block_text.lstrip(' '))

            # Only if we're in the leading whitespace region:
            if pos_in_block < leading_spaces:
                # Figure out how many spaces remain in this "tab chunk"
                chunk_end = ((pos_in_block // settings.tab_width) + 1) * settings.tab_width
                remove_count = min(chunk_end - pos_in_block, leading_spaces - pos_in_block)
                logging.info("Delete in leading indentation, removing %d spaces", remove_count)

                for _ in range(remove_count):
                    cursor.deleteChar()
                return True
        return False


    def _is_multiline_selection(self):
        """
        Returns True if selection spans more than one line, else False.
        """
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        start_block = self.document().findBlock(start).blockNumber()
        end_block = self.document().findBlock(end).blockNumber()
        return end_block > start_block

    def indent_code(self):
        """
        Indent either the selected lines (if multi-line selection)
        or just the current cursor position (if single-line or no selection).
        All changes happen in a single undo block.
        """
        logging.info("Indent code triggered")
        cursor = self.textCursor()
        cursor.beginEditBlock()

        if self._is_multiline_selection():
            logging.info("Multi-line selection detected -> Indenting each line")
            self._indent_selection()
        else:
            logging.info("Single-line (or no) selection -> Inserting indent at cursor")
            # Insert spacing at the current cursor position
            cursor.insertText(' ' * settings.tab_width)

        cursor.endEditBlock()

    def dedent_code(self):
        """
        Dedent either the selected lines (if multi-line selection)
        or just the current line (if single-line or no selection).
        All changes happen in a single undo block.
        """
        logging.info("Dedent code triggered")
        cursor = self.textCursor()
        cursor.beginEditBlock()

        if self._is_multiline_selection():
            logging.info("Multi-line selection detected -> Dedenting each line")
            self._dedent_selection()
        else:
            logging.info("Single-line (or no) selection -> Removing indent from current line if possible")
            line_start = cursor.block().position()
            leading_spaces = 0
            doc_text = cursor.block().text()
            for ch in doc_text:
                if ch == ' ':
                    leading_spaces += 1
                else:
                    break

            remove_spaces = min(settings.tab_width, leading_spaces)
            cursor.setPosition(line_start)
            for _ in range(remove_spaces):
                self._delete_forward_if_space(cursor)

        cursor.endEditBlock()

    def _indent_selection(self):
        """
        Increase indent for each selected line by settings.tab_width spaces.
        If no selection or selection on one line, that is handled outside.
        """
        logging.info("Indent selection (multi-line)")
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        start_block = self.document().findBlock(start).blockNumber()
        end_block = self.document().findBlock(end).blockNumber()

        # Work line by line
        for block_num in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(block_num)
            tmp_cursor = self.textCursor()
            tmp_cursor.setPosition(block.position())
            tmp_cursor.insertText(' ' * settings.tab_width)

    def _dedent_selection(self):
        """
        Decrease indent for each selected line by settings.tab_width spaces, 
        ensuring no reduction below zero.
        If no selection or selection on one line, that is handled outside.
        """
        logging.info("Dedent selection (multi-line)")
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        start_block = self.document().findBlock(start).blockNumber()
        end_block = self.document().findBlock(end).blockNumber()

        for block_num in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(block_num)
            line_text = block.text()
            leading_spaces = len(line_text) - len(line_text.lstrip(' '))

            remove_spaces = min(settings.tab_width, leading_spaces)

            tmp_cursor = self.textCursor()
            tmp_cursor.setPosition(block.position())
            for _ in range(remove_spaces):
                self._delete_forward_if_space(tmp_cursor)

    def _delete_forward_if_space(self, cursor):
        """
        Deletes one character if it is a space, used in dedent logic.
        """
        if cursor.document().characterAt(cursor.position()) == ' ':
            logging.info("Deleting forward space during dedent")
            cursor.deleteChar()

    def _insert_indentation(self, indent_count):
        """Insert the specified number of spaces at the cursor."""
        logging.info("Inserting indentation: %d spaces", indent_count)
        self.textCursor().insertText(' ' * indent_count)
