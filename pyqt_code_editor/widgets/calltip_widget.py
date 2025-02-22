from qtpy.QtCore import Qt
from qtpy.QtWidgets import QFrame, QLabel, QVBoxLayout
from .. import settings


class CalltipWidget(QFrame):
    """
    A small persistent widget to show calltip text so it won't vanish
    until explicitly hidden (unlike QToolTip).
    """
    def __init__(self, editor):
        # We set window flags separately (cannot OR widget attributes).
        super().__init__(editor)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        # WA_ShowWithoutActivating means the widget won’t take focus
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        # Make background translucent (use setAttribute):
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.apply_stylesheet()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        self._label = QLabel(self)
        self._label.setTextFormat(Qt.RichText)
        self._label.setWordWrap(True)
        layout.addWidget(self._label)
        self.setLayout(layout)

    def setText(self, text):
        self._label.setText(text)
        self.adjustSize()

    def apply_stylesheet(self):
        editor = self.parent()
        if editor.code_editor_colors is not None:
            self.setStyleSheet(f'''QFrame {{
                color: {editor.code_editor_colors['text']};
                background-color: {editor.code_editor_colors['background']};
                font: {settings.font_size}pt '{settings.font_family}';
                border-color: {editor.code_editor_colors['border']};
                border-width: 1px;
                border-style: solid;
                border-radius: 4px;
                padding: 8px;
            }}''')