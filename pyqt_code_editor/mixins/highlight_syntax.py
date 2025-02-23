from pygments.token import Token
from pygments.styles import get_style_by_name
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from qtpy.QtGui import QSyntaxHighlighter, QTextCharFormat, QBrush, QColor, QFont
from .. import settings
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class SyntaxHighlighter(QSyntaxHighlighter):
    """
    A standalone syntax highlighter that uses Pygments to highlight code
    in a QTextDocument. Merged from the original SyntaxHighlighter and
    PygmentsSH, removing PyQode dependencies and extra logic.
    """

    def __init__(self, document, lexer, color_scheme=None):
        super().__init__(document)
        self._lexer = lexer
        # If you have a custom ColorScheme, adapt here.
        # If color_scheme is a string, interpret it as a Pygments style name:
        self._color_scheme_name = color_scheme or "default"

        # Prepare a style from Pygments
        self._setup_style()
        self._token_formats = {}
        self._in_multiline_string = {}

    def _setup_style(self):
        """Initialize the Pygments style objects."""
        try:
            self._style = get_style_by_name(self._color_scheme_name)
        except Exception:
            logger.error(f"[PygmentsSyntaxHighlighter] style '{self._color_scheme_name}' not found")
            self._style = get_style_by_name("default")
        self._formatter = HtmlFormatter(style=self._style)

    def highlightBlock(self, text):
        """
        Called automatically by QSyntaxHighlighter for each line in the document.
        We tokenize the line with Pygments, then apply the relevant formats.
        """
        tokens = list(self._lexer.get_tokens(text))

        index = 0
        for token_type, token_text in tokens:
            length = len(token_text)
            fmt = self._get_format(token_type)
            self.setFormat(index, length, fmt)
            index += length
    

    def _get_format(self, token_type):
        """
        Retrieve (or create) a QTextCharFormat for the given Pygments token type.
        """
        if token_type in self._token_formats:
            return self._token_formats[token_type]

        fmt = QTextCharFormat()
        style_defs = self._style.style_for_token(token_type)

        if style_defs['color']:
            color_str = style_defs['color']
            fmt.setForeground(self._make_brush(color_str))
        if style_defs['bgcolor']:
            bg_color_str = style_defs['bgcolor']
            fmt.setBackground(self._make_brush(bg_color_str))
        if style_defs['bold']:
            fmt.setFontWeight(QFont.Bold)
        if style_defs['italic']:
            fmt.setFontItalic(True)
        if style_defs['underline']:
            fmt.setUnderlineStyle(QTextCharFormat.SingleUnderline)

        self._token_formats[token_type] = fmt
        return fmt

    def _make_brush(self, color_str):
        """Convert a hex string (e.g. 'fff' or 'ffffff') to a QBrush."""
        color_str = color_str.lstrip('#')
        if len(color_str) == 3:
            color_str = ''.join(ch * 2 for ch in color_str)
        red = int(color_str[0:2], 16)
        green = int(color_str[2:4], 16)
        blue = int(color_str[4:6], 16)
        return QBrush(QColor(red, green, blue))



class PythonSyntaxHighligter(SyntaxHighlighter):
    """Extends the default highlighter with support for multiline strings."""
    
    def highlightBlock(self, text):
        """
        1) Determine if this line starts as 'in' or 'out' of a triple-quoted string
           from the previous block's state.
        2) Scan for triple-quote transitions, toggling in/out state.
        3) If in triple-quote mode, highlight everything as a string, else use normal
           Pygments highlighting for this line.
        4) Use self.setCurrentBlockState(...) to mark the final state for this line, so
           that QSyntaxHighlighter can handle subsequent lines correctly.
        """
    
        # old_state is typically -1 for the very first block, otherwise what we last set
        old_state = self.previousBlockState()
        previously_in_string = (old_state == 1)
        currently_in_string = previously_in_string
    
        # Search line text for triple quotes
        triple_quotes = ('"""', "'''")
        idx = 0
        while True:
            next_quote_pos = -1
            found_quote = None
            for quote in triple_quotes:
                pos = text.find(quote, idx)
                if pos != -1 and (next_quote_pos == -1 or pos < next_quote_pos):
                    next_quote_pos = pos
                    found_quote = quote
    
            if next_quote_pos == -1:
                # No more triple quotes in this line
                break
            else:
                # Toggle the multiline string state
                currently_in_string = not currently_in_string
                # Move index past the found triple quotes
                idx = next_quote_pos + len(found_quote)
    
        if currently_in_string:
            # Highlight the entire line as string
            string_format = self._get_format(Token.String)
            self.setFormat(0, len(text), string_format)
            self.setCurrentBlockState(1)
        else:
            # Use normal Pygments line-by-line highlighting
            tokens = list(self._lexer.get_tokens(text))
            index = 0
            for token_type, token_text in tokens:
                token_len = len(token_text)
                fmt = self._get_format(token_type)
                self.setFormat(index, token_len, fmt)
                index += token_len
            self.setCurrentBlockState(0)    


class HighlightSyntax:
    """
    Mixin for QPlainTextEdit that instantiates a PygmentsSyntaxHighlighter and
    sets the QPlainTextEdit's background color from the associated style.
    """
    
    code_editor_color_scheme = 'monokai'
    code_editor_font_family = 'Ubuntu Mono'
    code_editor_font_size = 16    
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            lexer = get_lexer_by_name(self.code_editor_language)
        except Exception:
            logger.error(f"[HighlightSyntax] lexer '{self.code_editor_language}' not found")
            lexer = get_lexer_by_name('text')
        if self.code_editor_language == 'python':
            sh_cls = PythonSyntaxHighligter
        else:
            sh_cls = SyntaxHighlighter
        self._highlighter = sh_cls(self.document(),
                                   color_scheme=self.code_editor_color_scheme,
                                   lexer=lexer)
        style = self._highlighter._style
        self.code_editor_colors = {
            'background': style.background_color,
            'highlight': style.highlight_color,
            'text': '#' + style.style_for_token(Token.Text)['color'],
            'line-number': '#' + style.style_for_token(Token.Comment)['color'],
            'border': '#' + style.style_for_token(Token.Comment)['color']
        }
        self._apply_stylesheet()

    def refresh(self):
        super().refresh()
        self._highlighter.rehighlight()
        
    def update_theme(self):
        super().update_theme()
        self._apply_stylesheet()

    def _apply_stylesheet(self):
        stylesheet = f"""
            QPlainTextEdit {{
                background-color: {self.code_editor_colors['background']};
                font: {settings.font_size}pt '{settings.font_family}';
                color: {self.code_editor_colors['text']};
            }}
            QToolTip {{
                color: {self.code_editor_colors['text']};
                background-color: {self.code_editor_colors['background']};
                font: {settings.font_size}pt '{settings.font_family}';
                border-color: {self.code_editor_colors['border']};
                border-width: 1px;
                border-style: solid;
                border-radius: 4px;
                padding: 4px;
            }}
        """
        self.setStyleSheet(stylesheet)