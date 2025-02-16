from qtpy.QtCore import Qt
from qtpy.QtWidgets import QFrame, QLabel, QVBoxLayout


class CalltipWidget(QFrame):
    """
    A small persistent widget to show calltip text so it won't vanish
    until explicitly hidden (unlike QToolTip).
    """
    def __init__(self, parent=None):
        # We set window flags separately (cannot OR widget attributes).
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        # WA_ShowWithoutActivating means the widget won’t take focus
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        # Make background translucent (use setAttribute):
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.setWindowTitle("Calltip")
        self.setObjectName("_cm_calltip_widget")
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffe1;
                color: #000;
                border: 1px solid #a0a0a0;
                border-radius: 4px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        self._label = QLabel(self)
        self._label.setObjectName("_cm_calltip_label")
        self._label.setTextFormat(Qt.PlainText)
        layout.addWidget(self._label)
        self.setLayout(layout)

    def setText(self, text):
        self._label.setText(text)
        self.adjustSize()
