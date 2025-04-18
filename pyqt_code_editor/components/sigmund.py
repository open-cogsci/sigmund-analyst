from sigmund_qtwidget.sigmund_widget import SigmundWidget
from ..widgets import Dock
from .. import watchdog, settings
import textwrap
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class EditorWorkspace:
    def __init__(self, editor_panel):
        self._editor_panel = editor_panel
        self._indentation = ''
        
    def _get_indentation(self, content):
        dedented = textwrap.dedent(content)
        lines = content.splitlines()
        dedented_lines = dedented.splitlines()
    
        for original_line, dedented_line in zip(lines, dedented_lines):
            # Skip empty lines
            if original_line.strip():
                # Count leading whitespace
                orig_leading = len(original_line) - len(original_line.lstrip(' \t'))
                ded_leading = len(dedented_line) - len(dedented_line.lstrip(' \t'))
                # The difference should be the indentation sequence
                indentation_length = orig_leading - ded_leading
                if indentation_length > 0:
                    return original_line[:indentation_length]
                return ""
        # If no non-empty lines, return no indentation
        return ""
        
    def prepare(self, content):
        if content is None:
            return content
        return textwrap.indent(content, self._indentation)                
        
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
            content = self._normalize_line_breaks(text_cursor.selectedText())
        else:
            content = self._editor.toPlainText()
        self._indentation = self._get_indentation(content)
        logger.info(f'content was indented by "{self._indentation}"')        
        return content, self._editor.code_editor_language
    
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
        
        if content in (editor_content, self.strip_content(editor_content)):
            return False
        return True
    
    def strip_content(self, content):
        if content is None:
            return ''
        return content


class Sigmund(Dock):
    def __init__(self, parent, editor_panel):
        super().__init__('Sigmund', parent)
        self.setObjectName("sigmund")
        workspace = EditorWorkspace(editor_panel)
        self.sigmund_widget = SigmundWidget(self)
        self.sigmund_widget.setStyleSheet(f'font-size: {settings.font_size}pt')
        self.sigmund_widget.set_workspace_manager(workspace)
        self.setWidget(self.sigmund_widget)

    def setVisible(self, visible):
        if visible:
            logger.info('starting sigmund connector')
            self.sigmund_widget.start_server()
            watchdog.register_subprocess(self.sigmund_widget.server_pid)
        else:
            logger.info('stopping sigmund connector')
            self.sigmund_widget.stop_server()
        super().setVisible(visible)
