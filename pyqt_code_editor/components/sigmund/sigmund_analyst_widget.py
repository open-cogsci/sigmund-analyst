import os
from sigmund_qtwidget.sigmund_widget import SigmundWidget
import logging
logger = logging.getLogger(__name__)
        
        
class SigmundAnalystWidget(SigmundWidget):
    """Extends the default Sigmund widget with Sigmund Analyst-specific
    functionality.
    """
    def __init__(self, parent, editor_panel):    
        super().__init__(parent, application='Sigmund Analyst')
        self._editor_panel = editor_panel
        
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
