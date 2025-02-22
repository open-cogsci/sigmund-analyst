import logging
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import QTabWidget, QShortcut, QMessageBox
from qtpy.QtCore import Signal, Qt
from ..code_editors import PythonCodeEditor as CodeEditor
from .. import settings
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class TabbedEditor(QTabWidget):
    """A tab widget that can hold multiple CodeEditor instances."""
    lastTabClosed = Signal(QTabWidget)
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("TabbedEditor created")

        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.on_tab_close_requested)
        self._close_shortcut = QShortcut(QKeySequence.Close, self)
        self._close_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._close_shortcut.activated.connect(self.close_tab)
        # Use QKeySequence.PreviousChild to switch backwards
        self._prev_tab_shortcut = QShortcut(settings.shortcut_previous_tab, self)
        # self._prev_tab_shortcut = QShortcut(QKeySequence.PreviousChild, self)
        self._prev_tab_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._prev_tab_shortcut.activated.connect(self.previous_tab)
        
    def previous_tab(self):
        current_index = self.currentIndex()
        if current_index > 0:
            self.setCurrentIndex(current_index - 1)
        elif current_index == 0:
            self.setCurrentIndex(self.count() - 1)    
        
    def close_tab(self):
        current_index = self.currentIndex()
        if current_index >= 0:
            self.on_tab_close_requested(current_index)

    def on_tab_close_requested(self, index):        
        logger.info("Tab close requested for index: %s", index)
        widget = self.widget(index)
        if widget.modified:
            # Ask for confirmation before closing the tab
            result = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Do you want to save the changes before closing?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if result == QMessageBox.Yes:
                widget.save_file()                
            elif result == QMessageBox.Cancel:
                return
        if widget:
            widget.deleteLater()
        self.removeTab(index)

        # If no tabs remain, tell the outside world
        if self.count() == 0:
            logger.info("No tabs left in TabbedEditor => emit lastTabClosed")
            self.lastTabClosed.emit(self)
        else:
            # Making sure that one of the remaining editors gets focus
            if index > 0:
                index -= 1
            self.setCurrentIndex(index)
            self.widget(index).setFocus()
            
    def _on_modification_changed(self, changed):
        for index in range(self.count()):
            editor = self.widget(index)
            tab_text = self.tabText(index)
            if editor.modified and not tab_text.endswith(' *'):
                tab_text += ' *'
            elif not editor.modified and tab_text.endswith(' *'):
                tab_text = tab_text[:-1]
            self.setTabText(index, tab_text)

    def add_code_editor(self, path=None):
        editor = CodeEditor(self)
        editor.modification_changed.connect(self._on_modification_changed)
        logger.info("Adding new code editor tab")
        if path is not None:
            editor.open_file(path)
            title = editor.code_editor_file_path
        else:
            title = 'Untitled'
        index = self.addTab(editor, title)
        self.setCurrentIndex(index)
        return editor
    
