import textwrap
import logging
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
            # Move to the start of the first selected block
            start = text_cursor.selectionStart()
            end = text_cursor.selectionEnd()
            text_cursor.setPosition(start)
            text_cursor.movePosition(text_cursor.StartOfBlock)
            text_cursor.setPosition(end, text_cursor.KeepAnchor)
            text_cursor.movePosition(text_cursor.EndOfBlock, text_cursor.KeepAnchor)
            self._editor.setTextCursor(text_cursor)
            content = self._normalize_line_breaks(text_cursor.selectedText())
        else:
            content = self._editor.toPlainText()
        self._indentation = self._get_indentation(content)
        logger.info(f'content was indented by "{self._indentation}"')
        return textwrap.dedent(content), self._editor.code_editor_language
    
    def set(self, content, language):
        text_cursor = self._editor.textCursor()
        text_cursor.beginEditBlock()
        if text_cursor.hasSelection():
            text_cursor.insertText(content)
        else:
            text_cursor.select(text_cursor.Document)
            text_cursor.insertText(content)
        text_cursor.endEditBlock()
        self._editor.setTextCursor(text_cursor)
        self._editor.set_modified(True)
    
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
