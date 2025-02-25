from pygments.token import Token
from .. import settings
from ..syntax_highlighters.syntax_highlighter import create_syntax_highlighter
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class Theme:
    """
    Mixin for QPlainTextEdit that instantiates a PygmentsSyntaxHighlighter and
    sets the QPlainTextEdit's background color from the associated style.
    """
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._highlighter = create_syntax_highlighter(
            self.code_editor_language, self.document(),
            color_scheme=settings.color_scheme)
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