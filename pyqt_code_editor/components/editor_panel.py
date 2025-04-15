import os
from qtpy.QtWidgets import QApplication, QShortcut, QWidget, QHBoxLayout, QFileDialog
from qtpy.QtGui import QKeySequence
from qtpy.QtCore import Qt, Signal
from ..widgets import TabbedEditor, TabSplitter
from .. import settings, utils
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class EditorPanel(QWidget):
    
    open_folder_requested = Signal(str)
    
    def __init__(self, parent=None, initial_path=None):
        super().__init__(parent)
        logger.info("EditorPanel initialized")

        # Create a layout to hold the central_splitter as the sole widget
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._active_editor = None
        self._active_tab_widget = None

        # This 'central_splitter' can support 1 or 2 children by our assumption
        self.central_splitter = TabSplitter(self)
        layout.addWidget(self.central_splitter)

        self.initial_tab = self.create_tabbed_editor(initialize_empty=True)
        self.central_splitter.addWidget(self.initial_tab)
        
        self._split_h_shortcut = QShortcut(QKeySequence(settings.shortcut_split_horizontally), self)
        self._split_h_shortcut.activated.connect(lambda: self.split(Qt.Horizontal))

        self._split_v_shortcut = QShortcut(QKeySequence(settings.shortcut_split_vertically), self)
        self._split_v_shortcut.activated.connect(lambda: self.split(Qt.Vertical))

        self._open_shortcut = QShortcut(QKeySequence.Open, self)
        self._open_shortcut.activated.connect(lambda: self.select_and_open_file())

        self._new_shortcut = QShortcut(QKeySequence.New, self)
        self._new_shortcut.activated.connect(lambda: self.open_file())

        self._save_shortcut = QShortcut(QKeySequence.Save, self)
        self._save_shortcut.activated.connect(lambda: self.save_file())

        self._save_as_shortcut = QShortcut(QKeySequence.SaveAs, self)
        self._save_as_shortcut.activated.connect(lambda: self.save_file_as())        

    def create_tabbed_editor(self, initial_path=None, initialize_empty=False):
        """Utility to create a TabbedEditor and connect lastTabClosed so we can remove splits."""
        t = TabbedEditor(self)
        if initial_path is not None or initialize_empty:
            editor = t.add_code_editor(initial_path)
            editor.received_focus.connect(self._keep_track_of_active_editor)
        # Connect the lastTabClosed signal so that we can remove empty panels
        t.lastTabClosed.connect(self.handle_tabbed_editor_empty)
        t.tabCloseRequested.connect(self._relabel_tabs)
        t.open_folder_requested.connect(self.open_folder_requested)
        return t
    
    def unsaved_changes(self):
        return any(editor.modified for editor in self.central_splitter.editors())
        
    def save_all_unsaved_changes(self):
        for editor in self.central_splitter.editors():
            if editor.modified:
                editor.save_file()        
    
    def save_file(self):
        active_editor = self.active_editor()
        if active_editor is None:
            return
        active_editor.save_file()
        
    def save_file_as(self):
        active_editor = self.active_editor()
        if active_editor is None:
            return
        active_editor.save_file_as()
    
    def select_and_open_file(self):
        options = QFileDialog.Options()
        if os.environ.get("DONT_USE_NATIVE_FILE_DIALOG", False):
            options |= QFileDialog.Option.DontUseNativeDialog
            logger.info('not using native file dialog')        
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File", settings.current_folder, "All Files (*.*)",
            options=options)
        if path:
            settings.current_folder = os.path.dirname(path)
            self.open_file(path)
            
    def _keep_track_of_active_editor(self, editor):
        logger.info(f"active editor = {editor}")
        self._active_editor = editor
        self._active_tab_widget = self._active_editor.parent().parent()
    
    def open_file(self, path=None, line_number=None):
        if path is not None:
            # Don't allow the same file to be opened multiple times
            for editor in self.central_splitter.editors():
                if path == editor.code_editor_file_path:
                    # Make sure that the editor receives focus and is the
                    # current tab in its tab widget
                    tab_widget = editor.parent().parent()
                    tab_widget.setCurrentWidget(editor)
                    editor.setFocus()
                    if line_number is not None:
                        editor.jump_to_line(line_number)
                    return
        logger.info(f"Opening file from {path}.")
        active_tab_widget = self.active_tab_widget()
        # If currently there's only a dummy Untitled tab open, close it so that
        # we don't end up with lots of open dummy tabs
        if active_tab_widget.count() == 1:
            if active_tab_widget.tabText(0) == 'Untitled' \
                    and active_tab_widget.currentWidget().toPlainText() == '':
                # Remove the dummy tab
                active_tab_widget.removeTab(0)
        editor = active_tab_widget.add_code_editor(path)
        editor.received_focus.connect(self._keep_track_of_active_editor)
        editor.setFocus()
        if line_number is not None:
            editor.jump_to_line(line_number)
        self._relabel_tabs()
        
    def _relabel_tabs(self):
        """Relabels all tabs so that file names are shortned but unique."""
        paths = [editor.code_editor_file_path
                 for editor in self.central_splitter.editors()
                 if editor.code_editor_file_path is not None]    
        shortened_paths = utils.shorten_paths(paths)
        synonyms = {path: shortened_path
                    for path, shortened_path
                    in zip(paths, shortened_paths)}
        for tab_widget in self.central_splitter.tab_widgets():
            tab_widget.relabel_tabs(synonyms)
        

    def split(self, orientation):
        """
        Splits the focused panel. 
        1) Find the widget in focus (or the main splitter if none). 
        2) Find the index in the parent's splitter while it's still parented.
        3) Replace that index with a new splitter, containing the old widget + a fresh TabbedEditor.
        4) Use setSizes() so neither widget ends up at size=0 in the new splitter.
        """
        logger.info("Attempting to split with orientation '%s'",
                    "Horizontal" if orientation == Qt.Horizontal else "Vertical")
        active_tab_widget = self.active_tab_widget()
        if not active_tab_widget:
            logger.info("No focused TabbedEditor found; cannot split.")
            return

        # The parent is probably the main TabSplitter or another splitter
        parent_splitter = active_tab_widget.parentWidget()
        logger.info("Focused TabbedEditor parent: %s", type(parent_splitter))

        if not isinstance(parent_splitter, TabSplitter):
            logger.info("The focused TabbedEditor is not inside a TabSplitter. Cannot split further.")
            return

        # STEP 1: find which index in parent_splitter the old widget occupies
        idx_in_parent = None
        for i in range(parent_splitter.count()):
            if parent_splitter.widget(i) == active_tab_widget:
                idx_in_parent = i
                logger.info("Found old widget in parent's splitter at index %s", idx_in_parent)
                break

        if idx_in_parent is None:
            logger.warning("Could not find the old widget in the parent's splitter; skipping split.")
            return

        # STEP 2: create the new splitter and REPLACE at idx_in_parent
        logger.info("Creating a new TabSplitter with orientation '%s'",
                    "Horizontal" if orientation == Qt.Horizontal else "Vertical")
        new_splitter = TabSplitter(orientation, self)

        logger.info("Replacing parent's child at index %s with new_splitter", idx_in_parent)
        parent_splitter.replaceWidget(idx_in_parent, new_splitter)

        # STEP 3: re-parent the old tab widget into the new splitter
        logger.info("Re-parenting the focused TabbedEditor into the new_splitter")
        active_tab_widget.setParent(new_splitter)
        new_splitter.addWidget(active_tab_widget)

        # STEP 4: create a second TabbedEditor in the new splitter
        logger.info("Creating a second TabbedEditor to add to the new_splitter")
        new_tabs = self.create_tabbed_editor()
        new_code_editor = new_tabs.add_code_editor()
        new_code_editor.received_focus.connect(self._keep_track_of_active_editor)
        new_splitter.addWidget(new_tabs)

        # Ensure both get some space (the default ratio might make one "invisible")
        logger.info("Setting approximate sizes so neither splitter panel is collapsed")
        active_tab_widget.show()
        new_code_editor.setFocus()

    def active_tab_widget(self):
        """Return the QTabWidget that currently has focus, or None if not found."""
        if self._active_tab_widget and self._active_tab_widget.isVisible():
            return self._active_tab_widget
        # 1) Check if there's a currently focused widget in or under a QTabWidget.
        focus_widget = QApplication.focusWidget()
        while focus_widget:
            if isinstance(focus_widget, TabbedEditor):
                return focus_widget
            focus_widget = focus_widget.parentWidget()

        # 2) Fallback: if no QTabWidget is currently focused,
        # look through all children of EditorPanel and return the first QTabWidget you find.
        def find_first_tab_widget(widget):
            if isinstance(widget, TabbedEditor):
                return widget
            for child in widget.findChildren(QWidget):
                result = find_first_tab_widget(child)
                if result is not None:
                    return result
            return None

        return find_first_tab_widget(self)
    
    def active_editor(self):
        if self._active_editor and self._active_editor.isVisible():
            return self._active_editor
        active_tab_widget = self.active_tab_widget()
        if active_tab_widget is None:
            return None
        return active_tab_widget.currentWidget()
    
    def handle_tabbed_editor_empty(self, emptied_editor):
        """
        Called when a TabbedEditor becomes empty.
        1) Remove it from its parent splitter.
        2) Flatten any splitters that now have only one child left.
        """
        logger.info("handle_tabbed_editor_empty: %s", emptied_editor)

        parent_splitter = emptied_editor.parentWidget()
        if not isinstance(parent_splitter, TabSplitter):
            logger.info("The emptied TabbedEditor has no TabSplitter parent, ignoring.")
            return

        # Find index and remove it from the splitter
        idx_in_parent = None
        for i in range(parent_splitter.count()):
            if parent_splitter.widget(i) == emptied_editor:
                idx_in_parent = i
                break

        if idx_in_parent is None:
            logger.warning("handle_tabbed_editor_empty: cannot find editor in parent splitter")
            return

        # Remove from splitter
        logger.info("Removing emptied TabbedEditor from splitter at index %s", idx_in_parent)
        parent_splitter.replaceWidget(idx_in_parent, QWidget())  # put in a placeholder
        emptied_editor.setParent(None)
        emptied_editor.deleteLater()

        # Now collapse upwards if the parent splitter has 1 child left
        self._flatten_upwards(parent_splitter)
        
        editors = self.central_splitter.editors()
        # Make sure that an editor receives focus
        if editors:
            editors[0].setFocus()
        # If all editors were closed, create a new empty tab
        else:
            logger.info('all editors closed, initializing empty tab')
            self.initial_tab = self.create_tabbed_editor(initialize_empty=True)
            self.central_splitter.addWidget(self.initial_tab)

    def _flatten_upwards(self, splitter):
        """
        If a splitter (other than the central splitter) ends up with only 1 child,
        remove that splitter from its own parent and carry the child upward.
        Then continue up the chain. If it's the central splitter with 1 child which
        is itself a splitter, flatten that child into the central splitter.
        """
        logger.info("_flatten_upwards called for splitter=%s", splitter)

        # Remove placeholders (empty QWidget) from the splitter
        # so we don't count them as real children
        for i in range(splitter.count()):
            w = splitter.widget(i)
            # If the placeholder is a plain QWidget with no layout, remove it
            if isinstance(w, QWidget) and not isinstance(w, TabSplitter) and not isinstance(w, TabbedEditor):
                w.setParent(None)
                w.deleteLater()

        count = splitter.count()
        logger.info("Splitter %s now has %d children", splitter, count)

        # If there are 2 or more real children left, nothing to do
        if count >= 2:
            logger.info("Splitter has >=2 children, no flattening necessary.")
            return

        # If 0 left, remove this splitter from the parent's splitter as well
        if count == 0:
            logger.info("Splitter has 0 children, removing it from its parent.")
            self._remove_splitter_from_parent(splitter)
            return

        # If exactly 1 child remains
        single_child = splitter.widget(0)
        logger.info("Splitter has exactly 1 child: %s", single_child)

        # Is this the central splitter?
        if splitter == self.central_splitter:
            # The central splitter is allowed to have 1 child, but if that child is also a splitter
            # that has 2 children, flatten it.
            logger.info("Splitter is central_splitter, checking if we can flatten its single child.")
            if isinstance(single_child, TabSplitter):
                # We'll flatten that child's children directly into the central splitter
                self._flatten_child_splitter(self.central_splitter, single_child)
            else:
                logger.info("Single child is not a TabSplitter. No further flattening.")
            return
        else:
            # A normal splitter. We'll flatten it away.
            logger.info("Splitter is a normal splitter with 1 child. Flattening up one level.")
            self._remove_splitter_from_parent(splitter, single_child)

    def _remove_splitter_from_parent(self, splitter, single_child=None):
        """
        Removes splitter from its parent splitter. If single_child is given,
        that child is re-parented to the parent's parent, preserving order.
        """
        parent_splitter = splitter.parentWidget()
        if not isinstance(parent_splitter, TabSplitter):
            logger.info("Parent of this splitter is not another TabSplitter. Possibly main window. Doing nothing.")
            return

        # Find index of 'splitter' in parent_splitter
        idx_in_parent = None
        for i in range(parent_splitter.count()):
            if parent_splitter.widget(i) == splitter:
                idx_in_parent = i
                break

        if idx_in_parent is None:
            logger.warning("Could not find splitter in its own parent?!")
            return

        # If we're flattening and have a single child, we remove 'splitter' and
        # insert that single child in the same place
        if single_child is not None:
            logger.info("Flattening: re-parenting single_child %s up into parent splitter.", single_child)
            parent_splitter.replaceWidget(idx_in_parent, single_child)
            single_child.setParent(parent_splitter)
        else:
            # If 0 children left, just remove the splitter
            parent_splitter.replaceWidget(idx_in_parent, QWidget())
        splitter.setParent(None)
        splitter.deleteLater()

        # Now see if that parent splitter is left with 1 or 0 children after removing
        self._flatten_upwards(parent_splitter)

    def _flatten_child_splitter(self, parent_splitter, child_splitter):
        """
        Flatten child_splitter by removing it from parent_splitter and
        re-parenting its children directly into parent_splitter.
        """
        logger.info("Flattening child splitter %s in the central splitter %s", child_splitter, parent_splitter)

        # Find child_splitter index in parent_splitter
        idx_in_parent = None
        for i in range(parent_splitter.count()):
            if parent_splitter.widget(i) == child_splitter:
                idx_in_parent = i
                break
        if idx_in_parent is None:
            logger.warning("Could not find child splitter in parent splitter")
            return

        # We'll gather child_splitter's children
        child_widgets = []
        for i in range(child_splitter.count()):
            w = child_splitter.widget(i)
            child_widgets.append(w)

        # Replace the child_splitter with something temporary first
        parent_splitter.replaceWidget(idx_in_parent, QWidget())
        child_splitter.setParent(None)

        # Now, re-add those children directly to the parent_splitter
        for w in child_widgets:
            w.setParent(parent_splitter)
            parent_splitter.addWidget(w)
            
        # Give the parent splitter the same orientation as the child, because
        # the child should visually replace the parent
        parent_splitter.setOrientation(child_splitter.orientation())
        

        # Delete old splitter
        child_splitter.deleteLater()

        # Finally, see if that leaves parent_splitter with 1 or 0 children, and flatten if needed
        self._flatten_upwards(parent_splitter)
        
