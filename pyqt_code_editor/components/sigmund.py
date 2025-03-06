from qtpy.QtWidgets import QDockWidget
from qtpy.QtCore import Signal
from sigmund_qtwidget.sigmund_widget import SigmundWidget
import logging
logging.basicConfig(level=logging.debug)


class EditorWorkspace:
    def __init__(self, editor_panel):
        self._editor_panel = editor_panel
        
    @property
    def _editor(self):
        return self._editor_panel.active_editor()
    
    def _normalize_line_breaks(self, text):
        """Convert paragraph separators (U+2029) to standard newlines."""
        if text:
            return text.replace(u'\u2029', '\n')
        return text
    
    @property
    def content(self):
        text_cursor = self._editor.textCursor()
        if text_cursor.hasSelection():
            return self._normalize_line_breaks(text_cursor.selectedText())
        return self._editor.toPlainText()
    
    @property        
    def language(self):
        return self._editor.code_editor_language
    
    def get(self):
        text_cursor = self._editor.textCursor()
        if text_cursor.hasSelection():
            return self._normalize_line_breaks(text_cursor.selectedText()), self._editor.code_editor_language
        return self._editor.toPlainText(), self._editor.code_editor_language
    
    def set(self, content, language):
        text_cursor = self._editor.textCursor()
        if text_cursor.hasSelection():
            text_cursor.insertText(content)
            self._editor.setTextCursor(text_cursor)
        else:
            self._editor.setPlainText(content)
    
    def has_changed(self, content, language):
        text_cursor = self._editor.textCursor()
        if text_cursor.hasSelection():
            editor_content = self._normalize_line_breaks(text_cursor.selectedText())
        else:
            editor_content = self._editor.toPlainText()
        
        if not content:
            return False
        if content in (editor_content, self.strip_content(editor_content)):
            return False
        return True
    
    def strip_content(self, content):
        if content is None:
            return ''
        return content


class Sigmund(QDockWidget):
    """
    A very minimal QDockWidget that hosts SigmundWidget and doesn't handle
    functionality itself. It just overrides the close event.
    """

    close_requested = Signal()

    def __init__(self, parent, editor_panel):
        super().__init__(parent)
        self.setWindowTitle("Sigmund")

        # Create our SigmundWidget and place it inside this dock widget
        workspace = EditorWorkspace(editor_panel)
        self.sigmund_widget = SigmundWidget(self)
        self.sigmund_widget.set_workspace_manager(workspace)
        self.sigmund_widget.start_server()
        self.setWidget(self.sigmund_widget)

        # Override close event and emit a signal for the extension to handle
        def _close_event_override(event):
            event.ignore()
            self.hide()
            self.close_requested.emit()

        self.closeEvent = _close_event_override
