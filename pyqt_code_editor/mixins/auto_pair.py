from qtpy.QtCore import Qt
import logging
logging.basicConfig(level=logging.INFO, force=True)


class AutoPair:
    """
    Generic mixin for auto-pairing brackets/quotes/etc.
    
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

    def keyPressEvent(self, event):
        cursor = self.textCursor()
        old_pos = cursor.position()
        selected_text = cursor.selectedText()
        
        # Allows auto-pairing to be disabled for certain positions
        if self._disabled_for_position(old_pos):
            super().keyPressEvent(event)
            return
        
        # 1) Handle backspace for removing empty pairs like (|)
        if event.key() == Qt.Key_Backspace:
            if self._handle_auto_pair_backspace():
                return
        
        typed_char = event.text()
        
        # Pass the event up (inserts the typed_char)
        super().keyPressEvent(event)
        
        # 2) Possibly skip duplicate closing bracket/quote
        #    when the user manually types it.
        if typed_char and len(typed_char) == 1:
            for pair in self.PAIRS:
                if typed_char == pair["close_seq"]:
                    new_cursor = self.textCursor()
                    doc_text = self.toPlainText()
                    if (new_cursor.position() < len(doc_text) and
                        doc_text[new_cursor.position()] == typed_char):
                        # We remove the newly typed character and move cursor forward
                        new_cursor.beginEditBlock()
                        # Remove the bracket that was just typed
                        new_cursor.setPosition(old_pos)
                        new_cursor.deleteChar()
                        # Move cursor to skip the existing bracket
                        new_cursor.setPosition(old_pos + 1)
                        new_cursor.endEditBlock()
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
                                  selected_text)
                break


    def _handle_auto_pair_backspace(self) -> bool:
        """
        If the cursor is between an exact open_seq and close_seq pair (e.g., '(|)'),
        remove the full pair. Returns True if handled, False if not.
        """
        cursor = self.textCursor()
        pos = cursor.position()
        text = self.toPlainText()

        for pair in self.PAIRS:
            open_seq = pair["open_seq"]
            close_seq = pair["close_seq"]
            if open_seq and close_seq:
                l_open = len(open_seq)
                l_close = len(close_seq)
                
                # Make sure there's enough room before and after the cursor
                if pos >= l_open and pos + l_close <= len(text):
                    behind = text[pos - l_open : pos]
                    ahead = text[pos : pos + l_close]

                    # If the cursor is right between open_seq and close_seq
                    # with nothing typed in between (e.g. (|))
                    if behind == open_seq and ahead == close_seq:
                        c = self.textCursor()
                        c.beginEditBlock()
                        # Remove from open_seq start to close_seq end
                        c.setPosition(pos - l_open)
                        for _ in range(l_open + l_close):
                            c.deleteChar()
                        c.endEditBlock()

                        # Move cursor to the old open_seq start
                        c.setPosition(pos - l_open)
                        self.setTextCursor(c)
                        return True
        return False


    def _insert_pair(self, open_seq, close_seq, inbetween_seq, selected_text):
        """
        Called when we recognize that the user typed an open_seq in full.
        Insert the close_seq plus any inbetween_seq, and restore the cursor
        to the original position (right after the open_seq).
        """
        c = self.textCursor()
        
        # We'll remember where the user ended up (right after open_seq).
        old_pos = c.position()
        if inbetween_seq == '\n':
            # Get indentation level of block after cursor
            block = self.document().findBlock(old_pos)
            block_text = block.text()
            indent = block_text[:len(block_text) - len(block_text.lstrip())]        
            inbetween_seq = '\n' + indent
        # Insert the close_seq and inbetween_seq, indented to the same level as the block
        c.beginEditBlock()
                
        # Insert in-between text, then the closing
        c.insertText(selected_text + inbetween_seq + close_seq)
        
        # Move the cursor back so that it's right after the open_seq and (if any)
        # the selected text
        c.movePosition(c.Left, c.MoveAnchor, len(close_seq) + len(inbetween_seq))
        
        c.endEditBlock()
        self.setTextCursor(c)
        
        logging.info(
            "Auto-paired '%s' with '%s', inserted in-between '%s'. "
            "Cursor restored to position %d",
            open_seq, close_seq, inbetween_seq, old_pos
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