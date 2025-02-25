from pygments.styles import get_style_by_name
from pygments.formatters.html import HtmlFormatter
from qtpy.QtGui import QSyntaxHighlighter, QTextCharFormat, QBrush, QColor, QFont
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
