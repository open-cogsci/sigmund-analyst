import os
import logging
from qtpy.QtGui import QKeySequence, QIcon, QDrag, QPixmap, QPainter
from qtpy.QtWidgets import QTabWidget, QShortcut, QMessageBox, QMenu, QStyle, \
    QApplication, QTabBar
from qtpy.QtCore import Signal, Qt, QMimeData, QPoint, QByteArray, QDataStream
from ..code_editors import create_editor
from .. import settings, utils
from ..signal_router import signal_router
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class DraggableTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        # We use manual drag & drop, so disable Qt's built-in movable
        self.setMovable(False)
        self.dragStartPos = None
        self.dragIndex = -1
        self.draggedWidget = None
        self.draggedLabel = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragStartPos = event.position()
            # Save which tab was pressed
            self.dragIndex = self.tabAt(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return super().mouseMoveEvent(event)

        if self.dragStartPos is None or self.dragIndex < 0:
            return super().mouseMoveEvent(event)

        # If user moved far enough, start a drag
        distance = (event.position() - self.dragStartPos).manhattanLength()
        if distance > QApplication.startDragDistance():
            self.performDrag()
            return  # Once we start a drag, ignore further moves

        super().mouseMoveEvent(event)

    def performDrag(self):
        parentTabWidget = self.parentWidget()
        if not isinstance(parentTabWidget, QTabWidget):
            return

        # Extract the pressed tab's widget and text
        draggedWidget = parentTabWidget.widget(self.dragIndex)
        draggedText = parentTabWidget.tabText(self.dragIndex)
        draggedIcon = parentTabWidget.tabIcon(self.dragIndex)

        self.draggedWidget = draggedWidget
        # Temporary remove the tab from original location
        parentTabWidget.removeTab(self.dragIndex)

        # Prepare the Drag object
        drag = QDrag(self)
        mimeData = QMimeData()

        # we'll store the text, icon, and index in the mime data
        # For instance, we can store them in a QByteArray:
        dataByteArray = QByteArray()
        stream = QDataStream(dataByteArray, QDataStream.WriteOnly)
        # write text
        stream.writeQString(draggedText)
        # write an empty string if no icon
        hasIcon = not draggedIcon.isNull()
        stream.writeBool(hasIcon)
        if hasIcon:
            # For simplicity, store just an indicator that there's an icon
            # (Better approach might be to store a serialized pixmap)
            pass
        mimeData.setData("application/x-tabdata", dataByteArray)

        drag.setMimeData(mimeData)

        # Optional: show a preview pixmap
        # A simple approach is to build a pixmap with text:
        pixmap = QPixmap(150, 30)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, draggedText)
        painter.end()
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))

        # Start the drag
        dropAction = drag.exec(Qt.MoveAction)
        if dropAction != Qt.MoveAction:
            # If the drag was canceled, re-insert the tab in original location
            parentTabWidget.insertTab(self.dragIndex, draggedWidget, draggedIcon, draggedText)
        self.dragIndex = -1
        self.draggedWidget = None
        
        # Notify when the tab widget is empty
        if parentTabWidget.count() == 0:
            parentTabWidget.lastTabClosed.emit(parentTabWidget)

    def mouseReleaseEvent(self, event):
        # Reset drag info
        self.dragIndex = -1
        self.dragStartPos = None
        super().mouseReleaseEvent(event)


class TabbedEditor(QTabWidget):
    """A tab widget that can hold multiple CodeEditor instances."""
    lastTabClosed = Signal(QTabWidget)
    open_folder_requested = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("TabbedEditor created")
        self._synonyms = {}        
        self.tabCloseRequested.connect(self.on_tab_close_requested)

        # Existing shortcuts
        self._close_shortcut = QShortcut(QKeySequence.Close, self)
        self._close_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._close_shortcut.activated.connect(self.close_tab)

        # New shortcuts:
        self._close_all_shortcut = QShortcut(
            QKeySequence(settings.shortcut_close_all_tabs), self)
        self._close_all_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._close_all_shortcut.activated.connect(self.close_all_tabs)

        self._close_other_shortcut = QShortcut(
            QKeySequence(settings.shortcut_close_other_tabs), self)
        self._close_other_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._close_other_shortcut.activated.connect(
            lambda: self.close_other_tabs(self.currentIndex()))

        # Tab navigation shortcut
        self._prev_tab_shortcut = QShortcut(settings.shortcut_previous_tab, self)
        self._prev_tab_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._prev_tab_shortcut.activated.connect(self.previous_tab)

        # Replace default tab bar:
        self.setTabBar(DraggableTabBar(self))
        # Accept drops from other TabbedEditors
        self.setAcceptDrops(True)        

        # Enable custom context menus on the tab bar
        self.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabBar().customContextMenuRequested.connect(
            self._on_tabbar_context_menu)
        self.setTabsClosable(True)
        
    def relabel_tabs(self, synonyms):
        self._synonyms = synonyms
        for index in range(self.count()):
            editor = self.widget(index)
            path = editor.code_editor_file_path
            self.setTabText(index, self._synonym(path))
        
    def _synonym(self, path):
        if path is None:
            return 'Untitled'
        if path in self._synonyms:
            return self._synonyms[path]
        return os.path.basename(path)

    def previous_tab(self):
        current_index = self.currentIndex()
        if current_index > 0:
            self.setCurrentIndex(current_index - 1)
        elif current_index == 0:
            self.setCurrentIndex(self.count() - 1)    

    # -- New methods for closing multiple tabs --
    def close_all_tabs(self):
        """Close all tabs."""
        for i in reversed(range(self.count())):
            self.on_tab_close_requested(i)

    def close_other_tabs(self, index):
        """Close all tabs except the one at 'index'."""
        for i in reversed(range(self.count())):
            if i != index:
                self.on_tab_close_requested(i)

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
            
    def _on_modification_changed(self, editor, changed):
        index = self.indexOf(editor)
        tab_text = self.tabText(index)
        if editor.modified and not tab_text.endswith(' *'):
            tab_text += ' *'
        elif not editor.modified and tab_text.endswith(' *'):
            tab_text = tab_text[:-2]
        self.setTabText(index, tab_text)
        
    def _on_file_name_changed(self, editor, from_path, to_path):
        """When a file name has changed in such a way that the language has also
        changed, then we close and reopen the editor to make sure that the editor
        type is correct.
        """
        from_language = utils.guess_language_from_path(from_path)
        to_language = utils.guess_language_from_path(to_path)
        if from_language == to_language:
            return
        logger.info(f'language changed from {from_language} to {to_language}')
        index = self.indexOf(editor)
        self.removeTab(index)
        self.add_code_editor(to_path, index=index)

    def add_code_editor(self, path=None, index=None):
        editor = create_editor(path, parent=self)
        editor.modification_changed.connect(self._on_modification_changed)
        editor.file_name_changed.connect(self._on_file_name_changed)
        logger.info("Adding new code editor tab")
        title = self._synonym(editor.code_editor_file_path)
        if index is None:
            index = self.addTab(editor, title)
        else:
            self.insertTab(index, editor, title)        
        self.setCurrentIndex(index)
        signal_router.register_widget(editor)
        return editor
        
    def editors(self):
        """Returns a list of all editors in this tab widget"""
        return [self.widget(i) for i in range(self.count())]

    def _on_tabbar_context_menu(self, pos):
        """Show context menu with 'Close', 'Close All', 'Close Others' and icons."""
        index = self.tabBar().tabAt(pos)
        menu = QMenu(self)
        close_icon = QIcon.fromTheme(
            "window-close",
            self.style().standardIcon(QStyle.SP_DialogCloseButton))
        if index == -1:
            # Right-clicked on empty area
            close_all_action = menu.addAction("Close All")
            # Standard icon for "close" (fallback if "window-close" is not found)
            close_all_action.setIcon(close_icon)
            close_all_action.triggered.connect(self.close_all_tabs)
        else:
            # Right-clicked on a specific tab
            close_action = menu.addAction("Close")
            close_action.setIcon(close_icon)
            close_action.triggered.connect(
                lambda: self.on_tab_close_requested(index))

            close_all_action = menu.addAction("Close All")
            close_all_action.setIcon(close_icon)
            close_all_action.triggered.connect(self.close_all_tabs)

            close_others_action = menu.addAction("Close Others")
            # Using the same icon for "Close Others"
            close_others_action.setIcon(close_icon)
            close_others_action.triggered.connect(
                lambda: self.close_other_tabs(index))

        menu.exec_(self.tabBar().mapToGlobal(pos))
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-tabdata") or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-tabdata") or event.mimeData().hasUrls():
            # We can figure out which tab index we're hovering over
            # to show an appropriate "insertion" indicator.
            # For example, highlight the tab or something similar.
            # For brevity, we'll just accept the event and do no extra highlighting.
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        # If a file is dropped, open it in a new tab
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                # If path is a folder, open a code editor, otherwise emit the
                # open_folder signal
                if os.path.isdir(path):
                    self.open_folder_requested.emit(path)
                else:
                    self.add_code_editor(path)
        
        if not event.mimeData().hasFormat("application/x-tabdata"):
            event.ignore()
            return

        event.setDropAction(Qt.MoveAction)
        event.accept()

        # Extract tab data from the mime data
        dataByteArray = event.mimeData().data("application/x-tabdata")
        stream = QDataStream(dataByteArray, QDataStream.ReadOnly)
        tabText = stream.readQString()
        # (We ignore the icon detail in this example or simply set a blank icon.)
        # If you’re handing around pixmaps, you could store them more explicitly.

        # The source tab's DraggableTabBar has already removed it from its QTabWidget.
        # But we need the actual widget object that was being dragged. It's part
        # of the QDrag's source — we can find it by casting. We must be careful:
        sourceBar = event.source()
        if isinstance(sourceBar, DraggableTabBar):
            draggedWidget = sourceBar.draggedWidget
        else:
            draggedWidget = None

        # Insert the tab at the position that the user dropped on
        dropPos = event.position().toPoint()
        tabBar = self.tabBar()
        index = tabBar.tabAt(dropPos)
        if index < 0:
            # If the user dropped to the right of all existing tabs
            index = self.count()

        self.insertTab(index, draggedWidget, tabText)
        self.setCurrentIndex(index)
        