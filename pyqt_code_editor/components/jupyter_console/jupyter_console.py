from qtpy.QtWidgets import (QTabWidget, QWidget, QToolButton, QMenu,
                            QAction, QHBoxLayout)
from qtpy.QtCore import Signal
import qtawesome as qta
import sys
import logging
from ...environment_manager import environment_manager
from ...themes import HORIZONTAL_SPACING
from ...widgets import Dock
from .jupyter_console_tab import JupyterConsoleTab
from .kernel_spec_manager import HomeAwareKernelSpecManager
logger = logging.getLogger(__name__)


class JupyterConsole(Dock):
    """Dockable widget containing tabbed Jupyter consoles"""
    
    execution_complete = Signal(str, object)
    workspace_updated = Signal(dict)
    
    def __init__(self, parent=None, default_kernel='python3'):
        super().__init__("Jupyter Console", parent)
        self.setObjectName('jupyter_console')
        self.default_kernel = default_kernel

        # ---------------------------------------------------------------------
        # Kernel cache
        # ---------------------------------------------------------------------
        self.available_kernels = {}  # will be filled by refresh_kernel_menu()
        
        # ---------------------------------------------------------------------
        # UI setup
        # ---------------------------------------------------------------------
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.setWidget(self.tab_widget)
        
        # Corner widget with buttons
        corner_widget = QWidget()
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(0, 0, 0, 0)
        corner_layout.setSpacing(HORIZONTAL_SPACING)
        
        self.kernel_button = QToolButton()
        self.kernel_button.setIcon(qta.icon('mdi6.plus'))
        self.kernel_button.setToolTip("Add new kernel")
        self.kernel_button.setPopupMode(QToolButton.InstantPopup)
        self.kernel_button.setAutoRaise(True)
        corner_layout.addWidget(self.kernel_button)
        
        self.restart_button = QToolButton()
        self.restart_button.setIcon(qta.icon('mdi6.restart'))
        self.restart_button.setToolTip("Restart current kernel")
        self.restart_button.clicked.connect(self.restart_current_kernel)
        self.restart_button.setAutoRaise(True)
        corner_layout.addWidget(self.restart_button)
        
        self.interrupt_button = QToolButton()
        self.interrupt_button.setIcon(qta.icon('mdi6.stop'))
        self.interrupt_button.setToolTip("Interrupt current kernel (Ctrl+C)")
        self.interrupt_button.clicked.connect(self.interrupt_current_kernel)
        self.interrupt_button.setAutoRaise(True)
        corner_layout.addWidget(self.interrupt_button)
        
        self.tab_widget.setCornerWidget(corner_widget)
        
        # ---------------------------------------------------------------------
        # Kernel menu
        # ---------------------------------------------------------------------
        self.kernel_menu = QMenu(self.kernel_button)
        self.kernel_button.setMenu(self.kernel_menu)
        self.refresh_kernel_menu()
        
        # ---------------------------------------------------------------------
        # Start with a default kernel
        # ---------------------------------------------------------------------
        self.add_console_tab(self.default_kernel)
    
    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------
    def _on_tab_changed(self, index):
        console_tab = self.tab_widget.widget(index)
        if console_tab:
            console_tab.update_workspace()
            spec = self.available_kernels.get(console_tab.kernel_name, None)
            if spec:
                python_executable = spec['spec']['argv'][0]
            else:
                python_executable = sys.executable
            environment_manager.set_environment(console_tab.kernel_name,
                                                python_executable,
                                                'python')
    
    # -------------------------------------------------------------------------
    # Kernel handling
    # -------------------------------------------------------------------------
    def refresh_kernel_menu(self):
        """Refresh the list of available kernels and rebuild the kernel menu."""
        self.kernel_menu.clear()
        
        # Get available kernelspecs
        kernel_spec_manager = HomeAwareKernelSpecManager()
        self.available_kernels = kernel_spec_manager.get_all_specs()
        self.fallback_kernel = list(self.available_kernels.keys())[0]
        for spec_name, spec in self.available_kernels.items():
            display_name = spec['spec']['display_name']
            action = QAction(display_name, self)
            action.setData(spec_name)
            action.triggered.connect(self.kernel_menu_triggered)
            self.kernel_menu.addAction(action)
    
    def kernel_menu_triggered(self):
        action = self.sender()
        if action:
            self.add_console_tab(action.data())
    
    def add_console_tab(self, kernel_name):
        """Add a new console tab with the specified kernel.
        Falls back to the first available kernel if the requested one is invalid.
        """
        if kernel_name not in self.available_kernels:
            if self.available_kernels:
                logger.warning(
                    "Requested kernel '%s' not found. "
                    "Falling back to '%s'.", kernel_name, self.fallback_kernel
                )
                kernel_name = self.fallback_kernel
            else:
                logger.error("No available kernels found. Cannot create console tab.")
                return None
        
        console_tab = JupyterConsoleTab(kernel_name=kernel_name, parent=self)
        console_tab.execution_complete.connect(self.handle_execution_complete)
        console_tab.workspace_updated.connect(self.handle_workspace_updated)
        index = self.tab_widget.addTab(console_tab, kernel_name)
        self.tab_widget.setCurrentIndex(index)
        return console_tab
    
    # -------------------------------------------------------------------------
    # Tab / kernel management
    # -------------------------------------------------------------------------
    def close_tab(self, index):
        widget = self.tab_widget.widget(index)
        if widget:
            widget.shutdown_kernel()
            self.tab_widget.removeTab(index)
            if self.tab_widget.count() == 0:
                self.add_console_tab(self.default_kernel)
    
    def get_current_console(self):
        return self.tab_widget.currentWidget()
    
    def restart_current_kernel(self):
        console = self.get_current_console()
        if console:
            logger.info("Restarting current kernel")
            if console.restart_kernel():
                logger.info("Kernel restart initiated")
            else:
                logger.warning("Failed to restart kernel")
    
    def interrupt_current_kernel(self):
        console = self.get_current_console()
        if console:
            logger.info("Interrupting current kernel")
            if console.interrupt_kernel():
                logger.info("Interrupt signal sent to kernel")
            else:
                logger.warning("Failed to interrupt kernel")
    
    # -------------------------------------------------------------------------
    # Execution helpers
    # -------------------------------------------------------------------------
    def execute_code(self, code, silent=False):
        console = self.get_current_console()
        if console:
            (console.execute_silently if silent else console.execute_code)(code)
    
    def execute_file(self, filepath):
        console = self.get_current_console()
        if console:
            console.execute_file(filepath)
    
    def change_directory(self, directory):
        console = self.get_current_console()
        return console.change_directory(directory) if console else False
    
    # -------------------------------------------------------------------------
    # Signals
    # -------------------------------------------------------------------------
    def handle_execution_complete(self, output, result):
        self.execution_complete.emit(output, result)
        
    def handle_workspace_updated(self, data):
        self.workspace_updated.emit(data)