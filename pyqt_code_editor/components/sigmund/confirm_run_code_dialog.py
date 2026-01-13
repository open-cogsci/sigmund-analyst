from qtpy.QtWidgets import QVBoxLayout, QDialogButtonBox, QLabel, \
    QSizePolicy, QDialog, QSplitter
from qtpy.QtCore import Qt
import logging
from sigmund_qtwidget.chat_browser import ChatBrowser
from pyqt_code_editor.code_editors import create_editor

logger = logging.getLogger(__name__)

MAX_MESSAGE_HEIGHT = 200

class ConfirmRunCodeDialog(QDialog):
    """
    A modal dialog that displays code to be executed and asks the user to confirm or cancel.
    """

    def __init__(self, parent, code: str, language: str):
        super().__init__(parent)

        self.setWindowTitle(f"Confirm {language} code execution")

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Use ChatBrowser to display the AI message
        self.message_browser = ChatBrowser(self)
        self.message_browser.append_message(
            'ai', 'Sigmund wants to run the following code:')
        self.message_browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.message_browser.setMaximumHeight(MAX_MESSAGE_HEIGHT)

        # Create code editor for the code to be executed
        self.code_view = create_editor(language=language)
        self.code_view.setPlainText(code)
        self.code_view.setReadOnly(True)

        # Create a vertical splitter to hold the message browser and the code
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.message_browser)
        splitter.addWidget(self.code_view)
        layout.addWidget(splitter)

        # The disclaimer label
        disclaimer_label = QLabel(
            "Carefully review the code before execution. Executing code can have unintended consequences.",
            self
        )
        disclaimer_label.setWordWrap(True)
        disclaimer_label.setObjectName('control-warning')
        disclaimer_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(disclaimer_label)

        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.resize(800, 600)