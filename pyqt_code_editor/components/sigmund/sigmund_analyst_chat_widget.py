from qtpy.QtWidgets import QCheckBox, QWidget, QVBoxLayout
from sigmund_qtwidget.chat_widget import ChatWidget
from ... import settings


class SigmundAnalystChatWidget(ChatWidget):
    """Extended chat widget with Sigmund Analyst-specific options"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Create a container for the checkboxes
        options_container = QWidget()
        options_layout = QVBoxLayout(options_container)
        options_layout.setContentsMargins(5, 5, 5, 5)
        options_layout.setSpacing(2)
        # "Review proposed changes" checkbox
        self._review_actions_checkbox = QCheckBox(
            "Review Sigmund's actions (recommended)")
        self._review_actions_checkbox.setChecked(
            settings.sigmund_review_actions)
        self._review_actions_checkbox.stateChanged.connect(
            self._on_review_actions_changed)
        options_layout.addWidget(self._review_actions_checkbox)
        # Insert the options container before the input container
        main_layout = self.layout()
        main_layout.insertWidget(main_layout.count(), options_container)
        
    def _on_review_actions_changed(self, state):
        """Store the review changes setting."""
        settings.sigmund_review_actions = bool(state)
            
    def append_message(self, msg_type, text, scroll=True):
        if msg_type == 'ai' and '(Suggesting IDE action)' in text:
            text = '⚙️ Sigmund is working …'
        self._chat_browser.append_message(msg_type, text, scroll)        
