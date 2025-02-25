from qtpy.QtCore import Qt
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import QListWidget, QListWidgetItem
from .. import settings


class CompletionPopup(QListWidget):
    """
    A popup widget to display multiple completion suggestions,
    but it does NOT automatically grab focus or hide on focusOut
    so that it won't flicker when the user keeps typing in the editor.
    """
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self._completion_map = {}
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)        
        if editor.code_editor_colors is not None:
            self.setStyleSheet(f'''QListWidget {{
                color: {editor.code_editor_colors['text']};
                background-color: {editor.code_editor_colors['background']};
                font: {settings.font_size}pt '{settings.font_family}';
                border: 1px solid {editor.code_editor_colors['border']};
            }}''')
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
            self._completion_map[c['name']] = c['name']
            QListWidgetItem(c['name'], self)

        if not completions:
            self.hide()
            return

        # Place near the text cursor, taking into account that the viewport 
        # might change due to line numbers or other things to the left of the
        # editor
        cursor_rect = self.editor.cursorRect()
        cursor_rect.moveRight(cursor_rect.left() + self.editor.viewportMargins().left())
        global_pos = self.editor.mapToGlobal(cursor_rect.bottomLeft())
        self.move(global_pos)

        # Resize to fit the number of completions (within reason)
        self.setCurrentRow(0)
        self.resize(min(500, self.sizeHintForColumn(0) + 8),
                    min(500, self.sizeHintForRow(0) * len(completions) + 8))

        # If we are already visible, no need to hide/show
        # Just continue to show it in the new position.
        if not self.isVisible():
            self.show()
            
    def focusOutEvent(self, event):
        """
        We override focusOutEvent but don't hide the popup
        so we can continue showing suggestions while the editor has focus.
        """
        # If you want it to hide whenever it loses focus, uncomment:
        super().focusOutEvent(event)

    def insert_completion(self, item):
        """
        Inserts the selected completion text into the editor at the current cursor position.
        """
        if not item:
            return
        name = item.text()
        completion = self._completion_map.get(name)
        if not completion:
            return
        self.editor._cm_insert_completion(completion)
