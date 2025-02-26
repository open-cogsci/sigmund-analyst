from pygments.token import Token
from .. import settings
from ..syntax_highlighters.syntax_highlighter import create_syntax_highlighter
import logging
from qtpy.QtGui import QPainter, QColor, QFont, QFontMetrics
from qtpy.QtWidgets import QPlainTextEdit

logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

class Theme:
    """
    Mixin for QPlainTextEdit that provides theming. It handles the following:
    
    - Apply syntax highlighting
    - Set a stylesheet
    - Set code_editor_colors property so that other mixins can use it
    - Toggle visibility of character ruler (based on settings.character_ruler)
    - Toggle word wrap (based on settings.word_wrap)
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
        self._apply_word_wrap()
        self._apply_tab_width()

    def refresh(self):
        super().refresh()
        self._highlighter.rehighlight()
        
    def update_theme(self):
        super().update_theme()
        self._apply_stylesheet()
        self._apply_word_wrap()
        self._apply_tab_width
        self.viewport().update()

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

    def paintEvent(self, event):
        super().paintEvent(event)
        if settings.character_ruler:
            char_width = self.fontMetrics().width("x")
            x_pos = int(char_width * settings.character_ruler + self.contentOffset().x())
            y_pos = self.viewport().height()
            painter = QPainter(self.viewport())
            painter.setPen(QColor(self.code_editor_colors['line-number']))
            painter.drawLine(x_pos, 0, x_pos, y_pos)

    def _apply_word_wrap(self):
        """
        Toggles word wrap mode based on settings.word_wrap
        """
        if settings.word_wrap:
            self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        else:
            self.setLineWrapMode(QPlainTextEdit.NoWrap)

    def _apply_tab_width(self):
        """Sets the tab-stop distance. This uses a QFont rather than relying on
        the standard font metrics, because these are not immediately applied on
        initialization.
        """
        font = QFont()
        font.setFamily(settings.font_family)
        font.setPointSize(settings.font_size)
        self.setTabStopDistance(
            settings.tab_width * QFontMetrics(font).horizontalAdvance(' '))
     