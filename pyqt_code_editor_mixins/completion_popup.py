##########################################
# Updated completion_popup.py (example)
##########################################

from qtpy.QtCore import Qt
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import QListWidget, QListWidgetItem

class CompletionPopup(QListWidget):
    """
    A popup widget to display multiple completion suggestions,
    but it does NOT automatically grab focus or hide on focusOut
    so that it won't flicker when the user keeps typing in the editor.
    """
    def __init__(self, editor):
        super().__init__(None)
        self.editor = editor

        # Use a frameless tool window so it can float above the editor
        # without stealing focus. Note we do NOT use Qt.Popup here.
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)

        # Let the editor keep focus
        self.setFocusPolicy(Qt.NoFocus)

        # Single selection mode
        self.setSelectionMode(self.SingleSelection)

        # Insert the chosen completion when activated
        self.itemActivated.connect(self.insert_completion)

    def show_completions(self, completions):
        """
        Show/update the list of completions near the editor's cursor,
        without grabbing focus or hiding automatically.
        """
        self.clear()
        for c in completions:
            QListWidgetItem(c, self)

        if not completions:
            self.hide()
            return

        # Place near the text cursor
        cursor_rect = self.editor.cursorRect()
        global_pos = self.editor.mapToGlobal(cursor_rect.bottomLeft())
        self.move(global_pos)

        # Resize to fit the number of completions (within reason)
        self.setCurrentRow(0)
        self.resize(200, min(200, self.sizeHintForRow(0) * len(completions) + 8))

        # If we are already visible, no need to hide/show
        # Just continue to show it in the new position.
        if not self.isVisible():
            self.show()

    # def keyPressEvent(self, event):
    #     """
    #     If the user presses Enter/Tab while this has focus (i.e. user clicked),
    #     insert the completion. Otherwise, pass the event to the editor.
    #     """
    #     if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab):
    #         self.insert_completion(self.currentItem())
    #         event.accept()
    #         return
    #     elif event.key() == Qt.Key_Up:
    #         row = self.currentRow()
    #         self.setCurrentRow(max(0, row - 1))
    #         event.accept()
    #         return
    #     elif event.key() == Qt.Key_Down:
    #         row = self.currentRow()
    #         self.setCurrentRow(min(self.count() - 1, row + 1))
    #         event.accept()
    #         return
    #     elif event.key() == Qt.Key_Escape:
    #         self.hide()
    #         event.accept()
    #         return

    #     # For any other key, pass it back to the editor
    #     # This also means the popup will remain visible if the user typed
    #     # a character that triggers an updated completion list.
    #     self.hide()
    #     self.editor.setFocus()
    #     self.editor.keyPressEvent(event)

    def focusOutEvent(self, event):
        """
        We override focusOutEvent but don't hide the popup
        so we can continue showing suggestions while the editor has focus.
        """
        # If you want it to hide whenever it loses focus, uncomment:
        # self.hide()
        super().focusOutEvent(event)

    def insert_completion(self, item):
        """
        Inserts the selected completion text into the editor at the current cursor position.
        """
        if not item:
            return
        completion_text = item.text()
        cursor = self.editor.textCursor()
        cursor.insertText(completion_text)
        self.editor.setTextCursor(cursor)
        self.hide()
