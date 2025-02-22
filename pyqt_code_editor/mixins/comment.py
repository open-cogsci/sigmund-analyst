from qtpy.QtWidgets import QShortcut
from qtpy.QtGui import QKeySequence
from qtpy.QtCore import Qt
from .. import settings


class Comment:
    """
    A mixin class to add (un)commenting functionality to a QPlainTextEdit.
    """
    
    code_editor_comment_string = '# '

    def __init__(self, *args, **kwargs):
        """
        :param comment_string: The comment string to prepend for each line 
                               (default "# " for Python).
        """
        super().__init__(*args, **kwargs)
        # The text to prepend for a commented line
        self.code_editor_comment_string
        self._comment_shortcut = QShortcut(
            QKeySequence(settings.shortcut_comment), self)
        self._comment_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._comment_shortcut.activated.connect(self._toggle_comment)

    def _toggle_comment(self):
        """Toggle comment on the current selection or current line."""
        cursor = self.textCursor()
        if not cursor.hasSelection():
            # If no selection, just operate on the current line
            cursor.select(cursor.LineUnderCursor)

        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        # Re-select with partial offsets set to the entire lines
        cursor.setPosition(start)
        startBlock = cursor.blockNumber()
        cursor.setPosition(end, cursor.KeepAnchor)
        endBlock = cursor.blockNumber()

        # Decide whether to comment or uncomment
        all_commented = True
        for block_num in range(startBlock, endBlock + 1):
            block = self.document().findBlockByNumber(block_num)
            text = block.text()
            if text.strip() and not text.lstrip().startswith(self.code_editor_comment_string):
                all_commented = False
                break

        if all_commented:
            self._uncomment_blocks(startBlock, endBlock)
        else:
            self._comment_blocks(startBlock, endBlock)

    def _comment_blocks(self, start_block: int, end_block: int):
        """Comment all lines from start_block to end_block."""
        cursor = self.textCursor()
        cursor.beginEditBlock()  # group undo steps
        for block_num in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(block_num)
            if not block.isValid():
                continue
            text = block.text()
            # Insert comment string at first non-whitespace character
            leading_spaces = len(text) - len(text.lstrip())
            insert_position = block.position() + leading_spaces
            cursor.setPosition(insert_position)
            cursor.insertText(self.code_editor_comment_string)  
        cursor.endEditBlock()

    def _uncomment_blocks(self, start_block: int, end_block: int):
        """Uncomment all lines from start_block to end_block."""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for block_num in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(block_num)
            if not block.isValid():
                continue
            text = block.text()
            strip_len = len(self.code_editor_comment_string)
            # If the line is commented (discount leading whitespace), remove the comment string
            if text.lstrip().startswith(self.code_editor_comment_string):
                leading_spaces = len(text) - len(text.lstrip())
                remove_position = block.position() + leading_spaces
                cursor.setPosition(remove_position)
                cursor.setPosition(remove_position + strip_len, cursor.KeepAnchor)
                if cursor.selectedText() == self.code_editor_comment_string.rstrip('\r\n'):
                    cursor.removeSelectedText()
        cursor.endEditBlock()
