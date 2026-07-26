from qtpy.QtWidgets import (QCheckBox, QWidget, QVBoxLayout, QLabel,
                            QMessageBox)
from sigmund_qtwidget.chat_widget import ChatWidget
from ... import settings


class SigmundAnalystChatWidget(ChatWidget):
    """Extended chat widget with Sigmund Analyst-specific options"""

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = self.layout()
        # Warning banner shown when review is disabled (initially hidden)
        self._review_warning_label = QLabel(
            "⚠️ Review is disabled! Sigmund has full, unreviewed access to "
            "your computer's files and can execute arbitrary actions.")
        self._review_warning_label.setWordWrap(True)
        self._review_warning_label.setStyleSheet(
            "background-color: #ffcccc; color: #800000; "
            "padding: 10px; border-radius: 3px;")
        self._review_warning_label.setVisible(
            not settings.sigmund_review_actions)
        main_layout.insertWidget(0, self._review_warning_label)
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
        # 'Link editor (or selected text) to workspace' checkbox
        self._link_to_workspace_checkbox = QCheckBox(
            "Link active editor (or selected text) to workspace")
        self._link_to_workspace_checkbox.setChecked(
            settings.sigmund_link_to_workspace)
        self._link_to_workspace_checkbox.stateChanged.connect(
            self._on_link_to_workspace_changed)
        options_layout.addWidget(self._link_to_workspace_checkbox)
        # Insert the options container before the input container
        main_layout.insertWidget(main_layout.count(), options_container)

    def _on_review_actions_changed(self, state):
        """Store the review changes setting."""
        review = bool(state)
        if not review:
            reply = QMessageBox.warning(
                self,
                "Disable review?",
                "⚠️ Warning: By disabling review, Sigmund will have full, "
                "unreviewed access to your computer's files and can execute "
                "arbitrary actions without asking for confirmation first.\n\n"
                "Are you sure you want to disable review?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No)
            if reply != QMessageBox.Yes:
                # Revert the checkbox without triggering stateChanged again
                self._review_actions_checkbox.blockSignals(True)
                self._review_actions_checkbox.setChecked(True)
                self._review_actions_checkbox.blockSignals(False)
                return
        self._review_warning_label.setVisible(not review)
        settings.sigmund_review_actions = review

    def _on_link_to_workspace_changed(self, state):
        link_to_workspace = bool(state)
        sigmund_widget = self.parent()
        if link_to_workspace:
            sigmund_widget.set_workspace_manager(
                sigmund_widget._editor_workspace_manager)
        else:
            sigmund_widget.set_workspace_manager(None)
        settings.sigmund_link_to_workspace = link_to_workspace

