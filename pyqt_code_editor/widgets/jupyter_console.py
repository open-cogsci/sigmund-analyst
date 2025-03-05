from qtpy.QtWidgets import (QDockWidget, QTabWidget, QWidget, QVBoxLayout, 
                           QToolButton, QMenu, QAction)
from qtpy.QtCore import Signal
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.manager import QtKernelManager
from jupyter_client.kernelspec import KernelSpecManager
import os
from .. import settings


# Define some built-in themes
THEMES = {
    'light': {
        'background_color': '#FFFFFF',
        'text_color': '#000000',
        'selection_background': '#ADD6FF',
        'selection_color': '#000000',
    },
    'dark': {
        'background_color': '#1E1E1E',
        'text_color': '#D4D4D4',
        'selection_background': '#264F78',
        'selection_color': '#FFFFFF',
    },
    'monokai': {
        'background_color': '#272822',
        'text_color': '#F8F8F2',
        'selection_background': '#49483E',
        'selection_color': '#F8F8F2',
    },
    'solarized_light': {
        'background_color': '#FDF6E3',
        'text_color': '#657B83',
        'selection_background': '#EEE8D5',
        'selection_color': '#586E75',
    },
    'solarized_dark': {
        'background_color': '#002B36',
        'text_color': '#839496',
        'selection_background': '#073642',
        'selection_color': '#93A1A1',
    }
}


class JupyterConsoleTab(QWidget):
    """Individual tab containing a Jupyter console with its own kernel"""
    
    execution_complete = Signal(str, object)  # Signal for output interception
    
    def __init__(self, kernel_name=None, parent=None):
        super().__init__(parent)
        self.kernel_name = kernel_name or 'python3'
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
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

    
    def _setup_output_interception(self):
        """Set up output interception to capture kernel output"""
        # For out-of-process kernels, we need to use message handlers
        self.jupyter_widget.kernel_client.iopub_channel.message_received.connect(
            self._handle_iopub_message
        )
    
    def _handle_iopub_message(self, msg):
        """Handle messages from the kernel's IOPub channel"""
        msg_type = msg.get('msg_type', '')
        content = msg.get('content', {})
        
        # Capture execution results
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
    
    def execute_code(self, code):
        """Execute a code snippet in this kernel"""
        self.jupyter_widget.execute(code)
    
    def execute_file(self, filepath):
        """Execute a file in this kernel"""
        code = f"%run {filepath}"
        self.execute_code(code)
    
    def change_directory(self, directory):
        """Change the kernel's working directory"""
        if os.path.exists(directory):
            code = f"import os\nos.chdir(r'{directory}')"
            self.execute_code(code)
            return True
        return False
    
    def shutdown_kernel(self):
        """Shutdown the kernel"""
        self.kernel_client.stop_channels()
        self.kernel_manager.shutdown_kernel()


class JupyterConsole(QDockWidget):
    """Dockable widget containing tabbed Jupyter consoles"""
    
    execution_complete = Signal(str, object)  # Signal for output interception
    
    def __init__(self, parent=None, default_kernel='python3'):
        super().__init__("Jupyter Console", parent)
        self.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.default_kernel = default_kernel
        
        # Initialize the tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.setWidget(self.tab_widget)
        
        # Kernel selector in the corner
        self.kernel_button = QToolButton()
        self.kernel_button.setText("➕")
        self.kernel_button.setPopupMode(QToolButton.InstantPopup)
        self.tab_widget.setCornerWidget(self.kernel_button)
        
        # Create kernel menu
        self.kernel_menu = QMenu(self.kernel_button)
        self.kernel_button.setMenu(self.kernel_menu)
        self.refresh_kernel_menu()
        
        # Start with a default kernel
        self.add_console_tab(self.default_kernel)
    
    def refresh_kernel_menu(self):
        """Refresh the list of available kernels"""
        self.kernel_menu.clear()
        
        # Get available kernelspecs
        kernel_spec_manager = KernelSpecManager()
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
    
    def execute_code(self, code):
        """Execute code in the current console"""
        console = self.get_current_console()
        if console:
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
