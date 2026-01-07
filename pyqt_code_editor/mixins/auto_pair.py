from qtpy.QtCore import Qt
import logging
logger = logging.getLogger(__name__)


class AutoPair:
    """Generic mixin for auto-pairing brackets/quotes/etc.

    You can override self.PAIRS to add or remove different open/close
    sequences. Each entry is a dict with:
      - open_seq: string that triggers auto-pair (e.g. '(' or '\"\"\"')
      - close_seq: string that is inserted (e.g. ')' or '\"\"\"')
      - inbetween_seq: optional string inserted between open_seq and close_seq
                      (can be empty). e.g. '\n' for triple quotes.
    """

    PAIRS = [
        {"open_seq": "(", "close_seq": ")", "inbetween_seq": ""},
        {"open_seq": "[", "close_seq": "]", "inbetween_seq": ""},
        {"open_seq": "{", "close_seq": "}", "inbetween_seq": ""},
        {"open_seq": "\"", "close_seq": "\"", "inbetween_seq": ""},
        {"open_seq": "\'", "close_seq": "\'", "inbetween_seq": ""},
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setUndoRedoEnabled(True)
        # For scanning up to the max length of an open_seq
        self._max_open_len = max(len(pair["open_seq"]) for pair in self.PAIRS)
        self._trigger_chars = ''.join([pair['open_seq'] + pair['close_seq']
                                      for pair in self.PAIRS])

    def keyPressEvent(self, event):
        # Determine all relevant variables upfront
        typed_char = event.text()
        typed_key = event.key()
        cursor = self.textCursor()
        old_pos = cursor.position()
        selected_text = cursor.selectedText()
        doc_text = self.toPlainText()
        doc_len = len(doc_text)
        # If the old cursor position is beyond the length of the document, then
        # we don't need to do anything.
        if old_pos >= doc_len:
            super().keyPressEvent(event)
            return
        # Get character before cursor
        if old_pos > 0:
            char_before = doc_text[old_pos - 1]
        else:
            char_before = ""        
        # Get character after cursor
        if old_pos < doc_len:
            char_after = doc_text[old_pos]
        else:
            char_after = ""

        # If there is no opening (trigger character or backspace), then we 
        # don't need to do anything.
        if typed_char not in self._trigger_chars and typed_key != Qt.Key_Backspace:
            super().keyPressEvent(event)
            return

        # Don't autopair when there is no selection and the next character is
        # alphanumeric or underscore. This is for example when we're typing the
        # opening bracket of a list that is already completed
        if not selected_text:
            if char_after.isalnum() or char_after == "_":
                super().keyPressEvent(event)
                return

        # Allows auto-pairing to be disabled for certain positions
        if self._disabled_for_position(old_pos):
            super().keyPressEvent(event)
            return

        # 1) Handle backspace for removing empty pairs like (|)
        if typed_key == Qt.Key_Backspace:
            if self._handle_auto_pair_backspace(char_before, char_after, old_pos):
                super().keyPressEvent(event)
                return

        # Pass the event up (inserts the typed_char)
        super().keyPressEvent(event)

        # 2) Possibly skip duplicate closing bracket/quote
        #    when the user manually types it.
        if typed_char and len(typed_char) == 1:
            for pair in self.PAIRS:
                if typed_char == pair["close_seq"]:
                    new_cursor = self.textCursor()
                    new_pos = new_cursor.position()
                    new_doc_text = self.toPlainText()
                    new_doc_len = len(new_doc_text)
                    if new_pos < new_doc_len and new_doc_text[new_pos] == typed_char:
                        # We remove the newly typed character and move cursor forward
                        # Remove the bracket that was just typed
                        new_cursor.setPosition(old_pos)
                        new_cursor.deleteChar()
                        # Move cursor to skip the existing bracket
                        new_cursor.setPosition(old_pos + 1)
                        self.setTextCursor(new_cursor)
                    break

        # 3) After insertion, see if the text before the cursor matches an 'open_seq'
        #    If it does, insert close_seq + inbetween_seq, then restore cursor.
        new_cursor = self.textCursor()
        new_pos = new_cursor.position()
        text = self.toPlainText()

        # We'll scan backward from new_pos for up to _max_open_len chars
        start_search = max(0, new_pos - self._max_open_len)
        just_typed = text[start_search:new_pos]

        for pair in self.PAIRS:
            open_seq = pair["open_seq"]
            close_seq = pair["close_seq"]
            inbetween_seq = pair["inbetween_seq"]

            if just_typed.endswith(open_seq) and event.text() == text[new_pos - 1: new_pos]:
                self._insert_pair(open_seq, close_seq, inbetween_seq,
                                  selected_text, new_pos)
                break

    def _handle_auto_pair_backspace(self, char_before, char_after, pos) -> bool:
        """
        If the cursor is between an exact open_seq and close_seq pair (e.g., '(|)'),
        remove the following close_seq. The preceding open_seq will be removed 
        by the standard backspace. Only works for pairs of single characters.

        Args:
            char_before: The character before the cursor
            char_after: The character after the cursor
            pos: The cursor position

        Returns:
            True if handled, False if not.
        """
        # We need at least one character before and after cursor
        if not char_before or not char_after:
            return False

        # Check if they form a pair
        for pair in self.PAIRS:
            open_seq = pair["open_seq"]
            close_seq = pair["close_seq"]

            # Only handle single-character pairs
            if len(open_seq) != 1 or len(close_seq) != 1:
                continue

            if char_before == open_seq and char_after == close_seq:
                logger.info("deleting closing bracket")
                # Delete only the closing character
                cursor = self.textCursor()
                cursor.setPosition(pos)
                cursor.deleteChar()

                # The standard backspace will handle the opening character
                return True

        return False

    def _insert_pair(self, open_seq, close_seq, inbetween_seq, selected_text, cursor_pos):
        """
        Called when we recognize that the user typed an open_seq in full.
        Insert the close_seq plus any inbetween_seq, and restore the cursor
        to the original position (right after the open_seq).

        Args:
            open_seq: The opening sequence that was typed
            close_seq: The closing sequence to insert
            inbetween_seq: Text to insert between open and close
            selected_text: Text that was selected (if any)
            cursor_pos: Current cursor position (after the open_seq was inserted)
        """
        c = self.textCursor()

        if inbetween_seq == '\n':
            # Get indentation level of block after cursor
            block = self.document().findBlock(cursor_pos)
            block_text = block.text()
            indent = block_text[:len(block_text) - len(block_text.lstrip())]        
            inbetween_seq = '\n' + indent

        # Insert in-between text, then the closing
        c.insertText(selected_text + inbetween_seq + close_seq)

        # Move the cursor back so that it's right after the open_seq and (if any)
        # the selected text
        c.movePosition(c.Left, c.MoveAnchor, len(close_seq) + len(inbetween_seq))

        self.setTextCursor(c)

        logger.info(
            "Auto-paired '%s' with '%s', inserted in-between '%s'. "
            "Cursor restored to position %d",
            open_seq, close_seq, inbetween_seq, cursor_pos
        )

    def _disabled_for_position(self, pos):
        return False


class PythonAutoPair(AutoPair):
    PAIRS = [
        # Example triple quotes for Python:
        {"open_seq": "\"\"\"", "close_seq": "\"\"\"", "inbetween_seq": "\n"}, 
        {"open_seq": "'''",  "close_seq": "'''",  "inbetween_seq": "\n"},
        {"open_seq": "(", "close_seq": ")", "inbetween_seq": ""},
        {"open_seq": "[", "close_seq": "]", "inbetween_seq": ""},
        {"open_seq": "{", "close_seq": "}", "inbetween_seq": ""},
        {"open_seq": "\"", "close_seq": "\"", "inbetween_seq": ""},
        {"open_seq": "\'", "close_seq": "\'", "inbetween_seq": ""},
    ]

    def _disabled_for_position(self, pos):
        """
        Returns True if 'pos' (a QTextCursor.position() in self)
        is (likely) inside a comment in Python code by checking
        if there's a '#' before the cursor on this line.
        Otherwise returns False.
        """
        block = self.document().findBlock(pos)
        line_text = block.text()
        column = pos - block.position()

        # Find the first '#' in line_text
        hash_index = line_text.find('#')

        # If a '#' is found and it's to the left of the cursor, assume comment
        if hash_index != -1 and hash_index < column:
            return True

        return False