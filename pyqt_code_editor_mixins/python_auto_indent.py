import logging
logging.basicConfig(level=logging.INFO, force=True)
import re
from qtpy.QtCore import Qt


class PythonAutoIndent:
    """
    A mixin class to provide Python-specific auto-indentation,
    suitable for mixing into a QPlainTextEdit subclass.

    Added:
      - Info-level logging messages
      - Natural Backspace/Delete handling in leading indentation
    """

    INDENT_SIZE = 4
    DEDENT_KEYWORDS = {'elif', 'else', 'except', 'finally'}

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
            current_line = self._get_current_line_text()

            # Compute indentation for the next line
            new_indent = self._compute_newline_indent(current_line)
            super().keyPressEvent(event)  # Insert the newline first

            # Outdent if next line might start with a dedent keyword
            line_after_insert = self._get_current_line_text()
            for kw in self.DEDENT_KEYWORDS:
                if line_after_insert.strip().startswith(kw):
                    new_indent -= self.INDENT_SIZE
                    logging.info("Matching dedent keyword '%s' -> reduce indent", kw)
                    break

            # Ensure indentation is not negative
            new_indent = max(new_indent, 0)

            # Insert the computed indentation
            if new_indent > 0:
                logging.info("Inserting %d spaces of indentation", new_indent)
                self._insert_indentation(new_indent)
            return

        # Otherwise, default behavior
        super().keyPressEvent(event)

    def _handle_backspace(self):
        """
        If the cursor is in leading indentation, remove a 'tab chunk'
        of spaces (INDENT_SIZE), otherwise let the normal backspace happen.
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
                # i.e., from pos_in_block back to the multiple of INDENT_SIZE
                remainder = pos_in_block % self.INDENT_SIZE
                if remainder == 0:
                    remainder = self.INDENT_SIZE

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
        of spaces (INDENT_SIZE) going forward, otherwise let normal delete happen.
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
                chunk_end = ((pos_in_block // self.INDENT_SIZE) + 1) * self.INDENT_SIZE
                remove_count = min(chunk_end - pos_in_block, leading_spaces - pos_in_block)
                logging.info("Delete in leading indentation, removing %d spaces", remove_count)

                for _ in range(remove_count):
                    cursor.deleteChar()
                return True
        return False

    def _compute_newline_indent(self, line_text):
        """
        Given the current line of text, compute how many spaces
        the next line should be indented.
        """
        leading_spaces = len(line_text) - len(line_text.lstrip(' '))

        # Increase indentation if line ends with a colon or open bracket
        if line_text.rstrip().endswith(':'):
            logging.info("Line ends with ':', increasing indent by %d", self.INDENT_SIZE)
            leading_spaces += self.INDENT_SIZE
        elif self._ends_with_open_bracket(line_text):
            logging.info("Line ends with open bracket, increasing indent by %d", self.INDENT_SIZE)
            leading_spaces += self.INDENT_SIZE

        return leading_spaces

    def _ends_with_open_bracket(self, line_text):
        """Return True if the line ends with (, [, or { (ignoring whitespace)."""
        stripped = line_text.rstrip()
        return stripped and stripped[-1] in '([{'

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
            cursor.insertText(' ' * self.INDENT_SIZE)
    
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
            # Dedent only the line under the cursor if it has enough leading spaces
            line_start = cursor.block().position()
            leading_spaces = 0
            doc_text = cursor.block().text()
            for ch in doc_text:
                if ch == ' ':
                    leading_spaces += 1
                else:
                    break
    
            remove_spaces = min(self.INDENT_SIZE, leading_spaces)
            cursor.setPosition(line_start)
            for _ in range(remove_spaces):
                self._delete_forward_if_space(cursor)
    
        cursor.endEditBlock()
    
    def _indent_selection(self):
        """
        Increase indent for each selected line by INDENT_SIZE spaces.
        If no selection or selection on one line, this is handled outside.
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
            tmp_cursor.insertText(' ' * self.INDENT_SIZE)
    
    def _dedent_selection(self):
        """
        Decrease indent for each selected line by INDENT_SIZE spaces, 
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
    
            remove_spaces = min(self.INDENT_SIZE, leading_spaces)
    
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

    def _get_current_line_text(self):
        """
        Fetch the text of the line where the cursor is currently positioned.
        """
        cursor = self.textCursor()
        block = cursor.block()
        line = block.text()
        logging.info("Current line text: '%s'", line)
        return line
