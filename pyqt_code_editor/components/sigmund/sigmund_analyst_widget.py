import os
import time
from sigmund_qtwidget.sigmund_widget import SigmundWidget
from qtpy.QtCore import QEventLoop, QTimer
from qtpy.QtWidgets import QMessageBox, QDialog
from .sigmund_analyst_chat_widget import SigmundAnalystChatWidget
from .confirm_run_code_dialog import ConfirmRunCodeDialog
from ... import settings
import logging
logger = logging.getLogger(__name__)

ACTION_CANCELLED = 'I do not approve this action.'


class SigmundAnalystWidget(SigmundWidget):
    """Extends the default Sigmund widget with Sigmund Analyst-specific
    functionality.
    """
    chat_widget_cls = SigmundAnalystChatWidget

    def __init__(self, parent, editor_panel):
        super().__init__(parent, application='Sigmund Analyst')
        try:
            self._app = parent.parent()
            self._jupyter_console = self._app._jupyter_console
            # Connect the code_executed signal to a slot
        except AttributeError:
            logger.warning('No Jupyter console found.')
            self._jupyter_console = None
        else:
            self._jupyter_console.execution_complete.connect(
                self._handle_execution_result)
        self._editor_panel = editor_panel
        self._transient_settings = {
            'tool_ide_open_file': 'true',
            'tool_ide_execute_code': 'true'
        }
        # Store execution results
        self._execution_result = None
        self._execution_loop = None

    def _confirm_action(self, action_type, details):
        """Show a confirmation dialog for the proposed action.

        Args:
            action_type (str): Type of action (e.g., "open file", "execute code")
            details (str): Detailed information about the action

        Returns:
            bool: True if action is approved, False otherwise
        """
        if not settings.sigmund_review_actions:
            return True

        if action_type == "open file":
            return QMessageBox.question(
                self, 
                "Open file",
                f"Sigmund wants to open: \n\n{details}",
                QMessageBox.Ok | QMessageBox.Cancel,
                QMessageBox.Ok
            ) == QMessageBox.Ok
        dialog = ConfirmRunCodeDialog(
            self,
            action_type,
            details
        )
        return dialog.exec_() == QDialog.Accepted

    def _handle_execution_result(self, output, result):
        """Slot that handles the code_executed signal."""
        self._execution_result = (output, result)
        if self._execution_loop and self._execution_loop.isRunning():
            time.sleep(0.5)  # Wait for errors to appear
            self._execution_loop.quit()

    def run_command_open_file(self, path):
        if settings.sigmund_review_actions:
            if not QMessageBox.question(self, 
                                        "Confirm open file",
                                        f"Sigmund wants to open: \n\n{path}",
                                        QMessageBox.Ok | QMessageBox.Cancel,
                                        QMessageBox.Ok) == QMessageBox.Ok:
                return ACTION_CANCELLED
        try:
            self._editor_panel.open_file(path)
        except Exception as e:
            return f'Failed to open file: {e}'
        return f'Opened file: {path}'

    def run_command_execute_code(self, code, language):
        if settings.sigmund_review_actions:
            if not ConfirmRunCodeDialog(self, code, language).exec() \
                    == ConfirmRunCodeDialog.Accepted:
                return ACTION_CANCELLED
        if self._jupyter_console is None:
            return 'Code execution not supported.'
        self._app._toggle_dock_widget(self._jupyter_console, show=True)
        self._execution_result = None
        self._execution_loop = QEventLoop()
        QTimer.singleShot(30000, self._execution_loop.quit)  # 30 second timeout
        self._jupyter_console.execute_code(code)
        self._execution_loop.exec_()
        self._execution_loop = None
        if self._execution_result is None:
            return 'Code execution timed out or failed to return a result.'
        try:
            console_content = self._jupyter_console.get_current_console().jupyter_widget._control.toPlainText()
        except Exception as e:
            return f'Failed to get results from console content: {e}'
            console_content = ''
        console_content = '\n'.join(console_content.splitlines()[-100:])
        return f'# Console output (may be truncated):\n\n{console_content}'
    @property
    def _editor(self):
        return self._editor_panel.active_editor()        
        
    def send_user_message(self, text, *args, **kwargs):
        current_path = self._editor.code_editor_file_path
        # If the editor is not linked to a file, simply use the working 
        # directory.
        if current_path is None:
            current_path = '[unsaved file]'
            working_directory = os.getcwd()
        else:
            working_directory = os.path.dirname(current_path)

        # Initialize with default value
        working_directory_contents = "(No directory contents available)"

        # Get directory contents with priority to top-level items
        top_level = []
        all_items = []

        # Only wrap file system operations in try-except
        try:
            # Get top-level items (depth=1)
            top_level = [f for f in os.listdir(working_directory)
                        if os.path.isfile(os.path.join(working_directory, f))
                        or os.path.isdir(os.path.join(working_directory, f))]

            # Then get deeper items if we haven't reached our limit
            remaining_slots = max(0, 20 - len(top_level))
            if remaining_slots > 0:
                for root, dirs, files in os.walk(working_directory):
                    # Skip the top level since we already have it
                    if root == working_directory:
                        continue
                    # Add files first
                    for file in files:
                        if remaining_slots <= 0:
                            break
                        rel_path = os.path.relpath(os.path.join(root, file), working_directory)
                        all_items.append(f".\\{rel_path}")
                        remaining_slots -= 1
                    # Then add directories if we still have space
                    for dir in dirs:
                        if remaining_slots <= 0:
                            break
                        rel_path = os.path.relpath(os.path.join(root, dir), working_directory)
                        all_items.append(f".\\{rel_path}\\")
                        remaining_slots -= 1

            # Combine top level and deeper items
            working_directory_contents = "\n".join(
                sorted([f".\\{item}" if os.path.isfile(os.path.join(working_directory, item))
                 else f".\\{item}\\" for item in top_level] +
                all_items)
            )

            if len(top_level) + len(all_items) > 20:
                working_directory_contents += "\n... (additional files truncated)"

        except PermissionError:
            working_directory_contents = "(Could not read some directory contents - permission denied)"
        except OSError as e:
            working_directory_contents = f"(Could not read directory contents: {str(e)})"

        system_prompt = f'''## Working directory

The workspace corresponds to the following file: {current_path}
The working directory is: {working_directory}

Overview of working directory:

```
{working_directory_contents}
```
'''
        self._transient_system_prompt = system_prompt
        super().send_user_message(text, *args, **kwargs)
