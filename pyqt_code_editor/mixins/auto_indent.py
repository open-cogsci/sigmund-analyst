from qtpy.QtCore import Qt
from .. import settings
import logging
logging.basicConfig(level=logging.INFO, force=True)


class AutoIndent:
    """
    A generic mixin class to provide auto-indentation features for a QPlainTextEdit.
    Implements the following specs:

      1. Indentation Style Detection
         - detect_indentation_style() returns a string representing a single indentation
           (e.g. '\t' or '    ').
         - Currently, we return just '\t' by default (dummy implementation).

      2. Multiline Indent/Dedent
         - Tab in multi-line selection indents those lines by one chunk.
         - Shift+Tab (or Backtab) dedents those lines.

      3. Preserving Indentation on New Lines
         - Pressing Enter creates a new line with the same leading indentation
           (no language-specific logic).

      4. Single-Line Insert or Remove Indentation
         - Within a single line, Tab inserts one indentation chunk at the cursor location.
         - Shift+Tab removes up to one indentation chunk from the start of the line if possible.

      5. Handling Backspace and Delete in Leading Whitespace
         - Backspace/Delete in leading whitespace removes one indentation chunk worth of characters
           if they match the indentation style (e.g., one tab or up to len(indent_chunk) spaces).

      6. Completely Generic (No Language-Specific Rules)
         - No indentation changes based on braces, parentheses, or keywords.
    """

    def detect_indentation_style(self):
        """
        Dummy function that always returns a single-tab string for now.
        Later, this can analyze the document to decide if it should
        use tabs or spaces (e.g. '    ' for four spaces).
        """
        from detect_indent import detect_indent
        
        indent = detect_indent(self.toPlainText())
        if indent['type'] is None:
            return settings.default_indent
        return indent['indent']

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        logging.info("keyPressEvent: key=%s, modifiers=%s", key, modifiers)

        # Check for Tab/Shift+Tab indentation
        if key == Qt.Key_Tab and modifiers == Qt.NoModifier:
            logging.info("Tab pressed -> indent code")
            self.indent_code()
            return
        elif (key == Qt.Key_Tab and modifiers == Qt.ShiftModifier) or key == Qt.Key_Backtab:
            logging.info("Shift+Tab pressed -> dedent code")
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

        # Check for Enter/Return (preserve indentation)
        if key in (Qt.Key_Enter, Qt.Key_Return):
            logging.info("Enter/Return pressed -> preserve indentation on new line")
            cursor = self.textCursor()

            # Get leading whitespace of the current line
            block_text = cursor.block().text()
            leading_ws = len(block_text) - len(block_text.lstrip(' \t'))
            preserve_ws = block_text[:leading_ws]

            # Perform normal newline
            super().keyPressEvent(event)

            # Insert the same leading whitespace on the new line
            cursor.insertText(preserve_ws)
            self.setTextCursor(cursor)
            return

        # Default behavior for any other keys
        super().keyPressEvent(event)

    def _get_indent_string(self):
        """
        Returns the indentation chunk based on detect_indentation_style().
        By default, this is a single tab ('\t') but could be '    ' for spaces, etc.
        """
        return self.detect_indentation_style()

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
        or just the current cursor position (if single-line).
        """
        logging.info("indent_code triggered")
        cursor = self.textCursor()
        cursor.beginEditBlock()

        if self._is_multiline_selection():
            logging.info("Multi-line selection -> indent each line")
            self._indent_selection()
        else:
            logging.info("Single line -> insert indent at cursor")
            indent_str = self._get_indent_string()
            cursor.insertText(indent_str)

        cursor.endEditBlock()

    def dedent_code(self):
        """
        Dedent either the selected lines (if multi-line selection)
        or just the current line (if single-line).
        """
        logging.info("dedent_code triggered")
        cursor = self.textCursor()
        cursor.beginEditBlock()

        if self._is_multiline_selection():
            logging.info("Multi-line selection -> dedent each line")
            self._dedent_selection()
        else:
            logging.info("Single line -> remove up to one indent chunk from start")
            line_start = cursor.block().position()
            line_text = cursor.block().text()
            leading_ws = len(line_text) - len(line_text.lstrip(' \t'))

            chunk_size = self._compute_chunk_size()
            remove_chars = min(chunk_size, leading_ws)
            logging.info("Removing up to %d chars from leading whitespace", remove_chars)

            cursor.setPosition(line_start)
            for _ in range(remove_chars):
                self._delete_forward_if_tab_or_space(cursor)

        cursor.endEditBlock()

    def _indent_selection(self):
        """
        Increase indent for each selected line by one chunk.
        """
        logging.info("indent_selection (multi-line)")
        indent_str = self._get_indent_string()

        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        start_block = self.document().findBlock(start).blockNumber()
        end_block = self.document().findBlock(end).blockNumber()

        for block_num in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(block_num)
            tmp_cursor = self.textCursor()
            tmp_cursor.setPosition(block.position())
            tmp_cursor.insertText(indent_str)

    def _dedent_selection(self):
        """
        Decrease indent for each selected line by one chunk,
        ensuring we don't go below zero indentation.
        """
        logging.info("dedent_selection (multi-line)")
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        start_block = self.document().findBlock(start).blockNumber()
        end_block = self.document().findBlock(end).blockNumber()

        for block_num in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(block_num)
            line_text = block.text()
            leading_ws = len(line_text) - len(line_text.lstrip(' \t'))

            chunk_size = self._compute_chunk_size()
            remove_chars = min(chunk_size, leading_ws)

            tmp_cursor = self.textCursor()
            tmp_cursor.setPosition(block.position())
            for _ in range(remove_chars):
                self._delete_forward_if_tab_or_space(tmp_cursor)

    def _handle_backspace(self):
        """
        If the cursor is in leading indentation, remove one indentation chunk
        (based on the length of detect_indentation_style()).
        Returns True if handled, False otherwise.
        """
        cursor = self.textCursor()
        if not cursor.hasSelection():
            block_text = cursor.block().text()
            pos_in_block = cursor.positionInBlock()
            leading_ws = len(block_text) - len(block_text.lstrip(' \t'))

            # Only if we're in the leading whitespace region:
            if 0 < pos_in_block <= leading_ws:
                chunk_size = self._compute_chunk_size()
                remove_count = min(chunk_size, pos_in_block)
                logging.info("Backspace in leading whitespace -> removing %d chars", remove_count)

                for _ in range(remove_count):
                    cursor.deletePreviousChar()
                return True
        return False

    def _handle_delete(self):
        """
        If the cursor is in leading indentation, remove one indentation chunk going forward.
        Returns True if handled, False otherwise.
        """
        cursor = self.textCursor()
        if not cursor.hasSelection():
            block_text = cursor.block().text()
            pos_in_block = cursor.positionInBlock()
            leading_ws = len(block_text) - len(block_text.lstrip(' \t'))

            if pos_in_block < leading_ws:
                chunk_size = self._compute_chunk_size()
                remove_count = min(chunk_size, leading_ws - pos_in_block)
                logging.info("Delete in leading whitespace -> removing %d chars", remove_count)

                for _ in range(remove_count):
                    cursor.deleteChar()
                return True
        return False

    def _compute_chunk_size(self):
        """
        Returns the length of the indentation chunk returned by detect_indentation_style().
        For example, if detect_indentation_style() returns '\t', the size is 1;
        if it returns '    ', the size is 4, etc.
        """
        chunk = self.detect_indentation_style()
        return len(chunk)

    def _delete_forward_if_tab_or_space(self, cursor):
        """
        Deletes one character if it is a space or a tab in leading whitespace.
        (We remove characters one by one for partial or exact chunk removal.)
        """
        ch = cursor.document().characterAt(cursor.position())
        if ch in (' ', '\t'):
            cursor.deleteChar()