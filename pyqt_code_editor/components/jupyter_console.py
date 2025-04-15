from qtpy.QtWidgets import (QTabWidget, QWidget, QVBoxLayout, QToolButton, QMenu,
                            QAction, QHBoxLayout)
from qtpy.QtCore import Signal, QTimer
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.manager import QtKernelManager
from jupyter_client.kernelspec import KernelSpecManager
import qtawesome as qta
import os
import logging
import uuid
import json
from concurrent.futures import Future
from .. import settings
from ..themes import THEMES, OUTER_CONTENT_MARGINS, HORIZONTAL_SPACING
from ..widgets import Dock
from .. import watchdog
logger = logging.getLogger(__name__)


class HomeAwareKernelSpecManager(KernelSpecManager):
    """Reimplements the KernelSpecManager to always search in the Linux home
    folder. This for example ensures that the local kernels are picked up in a
    flatpak environment.
    """
    def _kernel_dirs_default(self) -> list[str]:
        dirs = super()._kernel_dirs_default()
        home_dir = os.path.expanduser("~")
        jupyter_kernel_dir = os.path.join(
            home_dir, '.local', 'share', 'jupyter', 'kernels')
        if os.path.isdir(jupyter_kernel_dir) and os.access(jupyter_kernel_dir,
                                                           os.R_OK):
            if jupyter_kernel_dir not in dirs:
                dirs.append(jupyter_kernel_dir)
        return dirs


class JupyterConsoleTab(QWidget):
    """Individual tab containing a Jupyter console with its own kernel"""
    
    execution_complete = Signal(str, object)  # Signal for output interception
    workspace_updated = Signal(dict)  # Signal for workspace updates
    
    def __init__(self, kernel_name=None, parent=None):
        super().__init__(parent)
        self.kernel_name = kernel_name or 'python3'
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(*OUTER_CONTENT_MARGINS)
        
        # Dictionary to track pending message results
        self._pending_messages = {}
        # Set of internal message IDs (for workspace queries, etc.)
        self._internal_messages = set()
        # Set of message IDs where output should be hidden
        self._silent_messages = set()
        
        # Create Jupyter console widget
        self.jupyter_widget = RichJupyterWidget()
        self.layout.addWidget(self.jupyter_widget)
        
        # Set up kernel - using out-of-process kernel
        self.kernel_manager = QtKernelManager(kernel_name=self.kernel_name)
        self.kernel_manager.start_kernel()
        
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()
        
        # Connect the console to the kernel
        self.jupyter_widget.kernel_manager = self.kernel_manager
        self.jupyter_widget.kernel_client = self.kernel_client
        
        # Set up output capture
        self._setup_output_interception()
        self.jupyter_widget.set_default_style(colors='linux')
        background_color = THEMES[settings.color_scheme]['background_color']
        stylesheet = f'''QPlainTextEdit, QTextEdit {{
                background-color: '{background_color}';
                background-clip: padding;
                color: white;
                font-size: {settings.font_size}pt;
                font-family: '{settings.font_family}';
                selection-background-color: #555;
            }}
            .inverted {{
                background-color: white;
                color: black;
            }}
            .error {{ color: red; }}
            .in-prompt-number {{ font-weight: bold; }}
            .out-prompt-number {{ font-weight: bold; }}
            .in-prompt,
            .in-prompt-number {{ color: lime; }}
            .out-prompt,
            .out-prompt-number {{ color: red; }}
        '''
        self.jupyter_widget.setStyleSheet(stylesheet)
        
        # Connect execution_complete to auto-update workspace
        self.execution_complete.connect(self._on_execution_complete)
    
    def _setup_output_interception(self):
        """Set up output interception to capture kernel output"""
        # Save reference to the original handler
        self._original_iopub_handler = self.jupyter_widget._dispatch        
        # Disconnect the original handler
        self.jupyter_widget.kernel_client.iopub_channel.message_received.disconnect(
            self._original_iopub_handler)        
        # Connect our handler first
        self.jupyter_widget.kernel_client.iopub_channel.message_received.connect(
            self._handle_iopub_message)
    
    def _handle_iopub_message(self, msg):
        """Handle messages from the kernel's IOPub channel"""
        msg_type = msg.get('msg_type', '')
        content = msg.get('content', {})
        parent_header = msg.get('parent_header', {})
        msg_id = parent_header.get('msg_id')
        
        # Check if this is a silent execution (output should be hidden)
        is_silent = msg_id in self._silent_messages
        
        # Check if this message is a response to a tracked request
        if msg_id in self._pending_messages:
            # Handle responses for workspace queries
            if msg_type == 'stream' and 'text' in content:
                future = self._pending_messages[msg_id]
                if not future.done():
                    try:
                        # Try to parse JSON output for workspace queries
                        output = content['text'].strip()
                        if output:
                            try:
                                data = json.loads(output)
                                future.set_result(data)
                            except json.JSONDecodeError:
                                future.set_result(output)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        future.set_exception(e)
                        
            # Check if response is complete
            elif msg_type == 'status' and content.get('execution_state') == 'idle':
                # Message processing is complete
                if msg_id in self._pending_messages:
                    future = self._pending_messages[msg_id]
                    # If the future is still not done, set an empty result
                    if not future.done():
                        future.set_result({})
                    # Clean up
                    self._cleanup_message_ids(msg_id)
        
        # Only emit execution_complete for non-internal messages
        if msg_id not in self._internal_messages:
            # Detect execution completion with status messages
            if not is_silent and msg_type == 'status' and content.get('execution_state') == 'idle':
                # This indicates the execution is complete, regardless of output
                
                self.execution_complete.emit('', {})            
            # Capture execution results for regular code execution
            if msg_type == 'execute_result':
                data = content.get('data', {})
                text_output = data.get('text/plain', '')
                self.execution_complete.emit(text_output, content)
            
            # Capture stdout/stderr
            elif msg_type in ('stream', 'display_data', 'error'):
                if msg_type == 'stream':
                    output = content.get('text', '')
                elif msg_type == 'display_data':
                    output = str(content.get('data', {}).get('text/plain', ''))
                else:  # error
                    output = '\n'.join(content.get('traceback', []))
                
                self.execution_complete.emit(output, content)
        
        # IMPORTANT: Only forward non-silent messages to the widget
        if not is_silent or msg_type not in ('execute_result', 'display_data',
                                             'stream', 'error'):
            self._original_iopub_handler(msg)
    
    def _cleanup_message_ids(self, msg_id):
        """Clean up message IDs from tracking sets"""
        self._pending_messages.pop(msg_id, None)
        self._internal_messages.discard(msg_id)
        self._silent_messages.discard(msg_id)
    
    def _on_execution_complete(self, output, content):
        """Automatically update workspace after regular code execution"""
        # Use a small delay to ensure the kernel has processed everything
        QTimer.singleShot(100, self.update_workspace)
    
    def update_workspace(self):
        """Trigger a workspace update and emit the signal when complete"""
        future = self.get_workspace_async()
        future.add_done_callback(self._on_workspace_update_complete)
    
    def _on_workspace_update_complete(self, future):
        """Handle completion of workspace update"""
        try:
            workspace_data = future.result()
            logger.info("Workspace updated")
            kernel_pid = workspace_data.pop('__kernel_pid', None)
            if kernel_pid is not None:
                watchdog.register_subprocess(kernel_pid)
            self.workspace_updated.emit(workspace_data)
        except Exception as e:
            logger.error(f"Error updating workspace: {e}")
            # Emit empty workspace on error
            self.workspace_updated.emit({})
    
    def execute_code(self, code):
        """Execute a code snippet in this kernel"""
        return self.jupyter_widget.execute(code)
    
    def execute_silently(self, code, internal=False, hide_output=True):
        """
        Execute code silently without showing it in the console
        
        Args:
            code (str): The code to execute
            internal (bool): If True, marks this as an internal query that 
                            shouldn't trigger workspace updates
            hide_output (bool): If True, hide any output generated by this execution
        """
        msg_id = self.kernel_client.execute(code, silent=True, store_history=False)
        if msg_id:
            if internal:
                self._internal_messages.add(msg_id)
            if hide_output:
                self._silent_messages.add(msg_id)
        return msg_id
        
    def execute_and_return_result(self, code, timeout=5.0):
        """Execute code silently and return the captured output synchronously"""
        future = self.execute_and_get_future(code)
        try:
            return future.result(timeout=timeout)
        except Exception as e:
            logger.error(f"Failed to get result: {e}")
            return None
            
    def execute_and_get_future(self, code):
        """Execute code silently and return a future for the result"""
        future = Future()
        msg_id = self.execute_silently(code, internal=True, hide_output=True)
        if not msg_id:
            future.set_result(None)
            return future
            
        self._pending_messages[msg_id] = future
        return future
    
    def get_workspace_async(self):
        """Asynchronously get the variables in the kernel's workspace"""
        # Create a unique variable name for results
        result_var = f"_workspace_data_{uuid.uuid4().hex[:8]}"
        
        # Define the code to execute in the kernel
        code = f"""
import sys
import os
import json

{result_var} = {{'__kernel_pid': os.getpid()}}

# Get all variables from globals
for __var_name, __var_value in list(globals().items()):
    # Skip internal variables and modules
    if __var_name.startswith('_') or __var_name == '{result_var}' \
            or __var_name in ('quit', 'exit', 'In', 'Out', 'get_ipython'):
        continue
    # Determine type
    __var_type = type(__var_value).__name__
    if __var_type in ('module', 'function', 'type'):
        continue
    
    # Create a preview based on type
    try:
        if __var_type == 'DataMatrix':
            __preview = f"DataMatrix: {{__var_value.shape}}"
        elif __var_type == 'DataFrame':
            __preview = f"DataFrame: {{__var_value.shape[0]}}×{{__var_value.shape[1]}}"
        elif __var_type == 'Series':
            __preview = f"Series: {{len(__var_value)}}"
        elif __var_type == 'ndarray':
            __preview = f"Array: {{__var_value.shape}}"
        elif __var_type in ('list', 'tuple', 'dict', 'set'):
            __preview = f"{{__var_type}}[{{len(__var_value)}}]"
        elif __var_type in ('str', 'int', 'float', 'bool'):
            # For simple types, just use repr with limits
            __preview = repr(__var_value)
            if len(__preview) > 50:
                preview = preview[:47] + '...'
        else:
            # For other types, just show the type
            __preview = f"{{__var_type}} object"
            
        {result_var}[__var_name] = {{'type': __var_type, 'preview': __preview}}
    except Exception as e:
        {result_var}[__var_name] = {{'type': __var_type, 'preview': f"<Error: {{str(e)}}>"}};

# Print as JSON for easy parsing
print(json.dumps({result_var}))
"""
        return self.execute_and_get_future(code)
    
    def execute_file(self, filepath):
        """Execute a file in this kernel"""
        code = f"%run {filepath}"
        self.execute_code(code)
    
    def change_directory(self, directory):
        """Change the kernel's working directory"""
        if os.path.exists(directory):
            code = f"import os\nos.chdir(r'{directory}')"
            self.execute_silently(code)
            return True
        return False    
    
    def interrupt_kernel(self):
        """Send interrupt (SIGINT) to the kernel"""
        if self.kernel_manager.has_kernel:
            logger.info(f"Sending interrupt to kernel {self.kernel_name}")
            self.kernel_manager.interrupt_kernel()
            return True
        return False
        
    def restart_kernel(self):
        """Restart the kernel"""
        if self.kernel_manager.has_kernel:
            logger.info(f"Restarting kernel {self.kernel_name}")
            self.jupyter_widget.request_restart_kernel()
            return True
        return False
    
    def shutdown_kernel(self):
        """Shutdown the kernel"""
        self.kernel_client.stop_channels()
        self.kernel_manager.shutdown_kernel()


class JupyterConsole(Dock):
    """Dockable widget containing tabbed Jupyter consoles"""
    
    execution_complete = Signal(str, object)  # Signal for output interception
    workspace_updated = Signal(dict)  # Signal for workspace updates
    
    def __init__(self, parent=None, default_kernel='python3'):
        super().__init__("Jupyter Console", parent)
        self.setObjectName('jupyter_console')
        self.default_kernel = default_kernel
        
        # Initialize the tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.setWidget(self.tab_widget)
        
        # Create corner widget with multiple buttons
        corner_widget = QWidget()
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(0, 0, 0, 0)
        corner_layout.setSpacing(HORIZONTAL_SPACING)
        
        # Add kernel button (for new kernels)
        self.kernel_button = QToolButton()
        self.kernel_button.setIcon(qta.icon('mdi6.plus'))
        self.kernel_button.setToolTip("Add new kernel")
        self.kernel_button.setPopupMode(QToolButton.InstantPopup)
        self.kernel_button.setAutoRaise(True)  # Make the button flat
        corner_layout.addWidget(self.kernel_button)
        
        # Add restart kernel button
        self.restart_button = QToolButton()
        self.restart_button.setIcon(qta.icon('mdi6.restart'))
        self.restart_button.setToolTip("Restart current kernel")
        self.restart_button.clicked.connect(self.restart_current_kernel)
        self.restart_button.setAutoRaise(True)  # Make the button flat
        corner_layout.addWidget(self.restart_button)
        
        # Add interrupt kernel button
        self.interrupt_button = QToolButton()
        self.interrupt_button.setIcon(qta.icon('mdi6.stop'))
        self.interrupt_button.setToolTip("Interrupt current kernel (Ctrl+C)")
        self.interrupt_button.clicked.connect(self.interrupt_current_kernel)
        self.interrupt_button.setAutoRaise(True)  # Make the button flat
        corner_layout.addWidget(self.interrupt_button)
        
        # Set the corner widget
        self.tab_widget.setCornerWidget(corner_widget)
        
        # Create kernel menu
        self.kernel_menu = QMenu(self.kernel_button)
        self.kernel_button.setMenu(self.kernel_menu)
        self.refresh_kernel_menu()
        
        # Start with a default kernel
        self.add_console_tab(self.default_kernel)
        
    def _on_tab_changed(self, index):
        console_tab = self.tab_widget.widget(index)
        console_tab.update_workspace()
    
    def refresh_kernel_menu(self):
        """Refresh the list of available kernels"""
        self.kernel_menu.clear()
        
        # Get available kernelspecs
        kernel_spec_manager = HomeAwareKernelSpecManager()
        specs = kernel_spec_manager.get_all_specs()
        
        for spec_name, spec in specs.items():
            display_name = spec['spec']['display_name']
            action = QAction(display_name, self)
            action.setData(spec_name)
            action.triggered.connect(self.kernel_menu_triggered)
            self.kernel_menu.addAction(action)
    
    def kernel_menu_triggered(self):
        """Handle kernel menu item selection"""
        action = self.sender()
        if action:
            kernel_name = action.data()
            self.add_console_tab(kernel_name)
    
    def add_console_tab(self, kernel_name):
        """Add a new console tab with the specified kernel"""
        # Create and add the new tab
        console_tab = JupyterConsoleTab(kernel_name=kernel_name, parent=self)
        console_tab.execution_complete.connect(self.handle_execution_complete)
        console_tab.workspace_updated.connect(self.handle_workspace_updated)
        index = self.tab_widget.addTab(console_tab, kernel_name)
        self.tab_widget.setCurrentIndex(index)
        return console_tab
    
    def close_tab(self, index):
        """Close a console tab and shut down its kernel"""
        widget = self.tab_widget.widget(index)
        if widget:
            # Shut down the kernel
            widget.shutdown_kernel()
            
            # Remove the tab
            self.tab_widget.removeTab(index)
            
            # If that was the last tab, add a new one with the default kernel
            if self.tab_widget.count() == 0:
                self.add_console_tab(self.default_kernel)
    
    def get_current_console(self):
        """Get the currently active console tab"""
        return self.tab_widget.currentWidget()
    
    def restart_current_kernel(self):
        """Restart the kernel in the current tab"""
        console = self.get_current_console()
        if console:
            logger.info("Restarting current kernel")
            success = console.restart_kernel()
            if success:
                logger.info("Kernel restart initiated")
            else:
                logger.warning("Failed to restart kernel")
    
    def interrupt_current_kernel(self):
        """Send interrupt signal to the current kernel"""
        console = self.get_current_console()
        if console:
            logger.info("Interrupting current kernel")
            success = console.interrupt_kernel()
            if success:
                logger.info("Interrupt signal sent to kernel")
            else:
                logger.warning("Failed to interrupt kernel")
    
    def execute_code(self, code, silent=False):
        """Execute code in the current console"""
        console = self.get_current_console()
        if console:
            if silent:
                console.execute_silently(code)
            else:
                console.execute_code(code)
    
    def execute_file(self, filepath):
        """Execute a file in the current console"""
        console = self.get_current_console()
        if console:
            console.execute_file(filepath)
    
    def change_directory(self, directory):
        """Change working directory of the current console"""
        console = self.get_current_console()
        if console:
            return console.change_directory(directory)
        return False
    
    def handle_execution_complete(self, output, result):
        """Handle execution complete signal from a console tab"""
        self.execution_complete.emit(output, result)
        
    def handle_workspace_updated(self, dict):
        """Handle workspace updated signal from a console tab"""
        self.workspace_updated.emit(dict)
