import os
import logging
from qtpy.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLineEdit,
    QListView,
    QAbstractItemView,
    QApplication
)
from qtpy.QtCore import Qt, QSortFilterProxyModel, QModelIndex
from qtpy.QtGui import QStandardItemModel, QStandardItem

logger = logging.getLogger(__name__)

class MultiNeedleFilterProxyModel(QSortFilterProxyModel):
    """
    Custom proxy model that splits the user input string into
    multiple tokens (space-delimited). Each token must appear
    somewhere in the item text (case-insensitive) for it to match.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._needles = []

    def setFilterString(self, text):
        # Split on whitespace to get multiple tokens
        self._needles = text.strip().split()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if not self._needles:
            return True  # If no input, show all
        index = self.sourceModel().index(source_row, 0, source_parent)
        item_text = index.data(Qt.DisplayRole) or ""
        item_text_lower = item_text.lower()

        # Each needle must be present in the text
        for needle in self._needles:
            needle = needle.lower()
            if needle not in item_text_lower:
                return False
        return True

class QuickOpenDialog(QDialog):
    """
    A generic quick-open dialog for filtering and selecting from a list of items, each a dict
    with at least a 'name' key.

    Subclasses should override on_item_selected(item_dict) to handle the chosen item.
    """
    def __init__(self, parent, items, title="Quick Open"):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.ApplicationModal)

        self.setWindowTitle(title)
        self.resize(400, 400)

        layout = QVBoxLayout(self)
        self._filter_edit = QLineEdit(self)
        self._filter_edit.setPlaceholderText("Type to filter...")
        layout.addWidget(self._filter_edit)

        self._list_view = QListView(self)
        self._list_view.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self._list_view)

        self._items = items
        self._item_model = QStandardItemModel(self)
        self._proxy_model = MultiNeedleFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._item_model)
        self._list_view.setModel(self._proxy_model)

        # Populate the model with items
        self._populate_model()

        # Ensure we select the top item whenever the filter results change
        self._proxy_model.layoutChanged.connect(self._select_top_item_if_available)

        # Connect signals
        self._filter_edit.textChanged.connect(self._proxy_model.setFilterString)
        self._list_view.doubleClicked.connect(self._on_item_double_clicked)

        # Attempt to select top item immediately
        self._select_top_item_if_available()

    def _populate_model(self):
        for item_dict in self._items:
            name = item_dict.get("name", "")
            item = QStandardItem(name)
            # Store the entire dict in UserRole
            item.setData(item_dict, Qt.UserRole)
            self._item_model.appendRow(item)

    def _on_item_double_clicked(self, proxy_index: QModelIndex):
        source_index = self._proxy_model.mapToSource(proxy_index)
        item = self._item_model.itemFromIndex(source_index)
        item_dict = item.data(Qt.UserRole)
        self.on_item_selected(item_dict)
        self.accept()

    def _select_top_item_if_available(self):
        """Select the top item if it exists, otherwise clear selection."""
        count = self._proxy_model.rowCount()
        if count > 0:
            top_index = self._proxy_model.index(0, 0)
            self._list_view.setCurrentIndex(top_index)
        else:
            self._list_view.clearSelection()

    def on_item_selected(self, item_dict: dict):
        """
        Override this in subclasses to define what happens when an item is chosen.
        """
        raise NotImplementedError("Subclasses must implement on_item_selected()")

    def keyPressEvent(self, event):
        """Handle Enter for selection and Up/Down wrap-around navigation."""
        key = event.key()
        count = self._proxy_model.rowCount()

        # If there are no matches, ignore arrow and page navigation
        if count == 0:
            if key in (
                Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown,
                Qt.Key_Home, Qt.Key_End
            ):
                return

        if key in (Qt.Key_Return, Qt.Key_Enter):
            current_index = self._list_view.currentIndex()
            if current_index.isValid():
                proxy_index = current_index
            else:
                # If nothing is selected, fall back to top item if available
                proxy_index = self._proxy_model.index(0, 0) if count > 0 else None

            if proxy_index is not None and proxy_index.isValid():
                source_index = self._proxy_model.mapToSource(proxy_index)
                item = self._item_model.itemFromIndex(source_index)
                item_dict = item.data(Qt.UserRole)
                self.on_item_selected(item_dict)
            self.accept()

        elif key == Qt.Key_Up:
            if count > 0:
                current_index = self._list_view.currentIndex()
                if current_index.isValid():
                    row = current_index.row()
                    if row <= 0:
                        # wrap to last
                        self._list_view.setCurrentIndex(
                            self._proxy_model.index(count - 1, 0)
                        )
                    else:
                        self._list_view.setCurrentIndex(
                            self._proxy_model.index(row - 1, 0)
                        )
                else:
                    # If nothing is selected, go to last
                    self._list_view.setCurrentIndex(
                        self._proxy_model.index(count - 1, 0)
                    )
            return

        elif key == Qt.Key_Down:
            if count > 0:
                current_index = self._list_view.currentIndex()
                if current_index.isValid():
                    row = current_index.row()
                    if row >= count - 1:
                        # wrap to first
                        self._list_view.setCurrentIndex(
                            self._proxy_model.index(0, 0)
                        )
                    else:
                        self._list_view.setCurrentIndex(
                            self._proxy_model.index(row + 1, 0)
                        )
                else:
                    # If nothing is selected, go to first
                    self._list_view.setCurrentIndex(
                        self._proxy_model.index(0, 0)
                    )
            return

        elif key in (Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End):
            # Let default navigation logic handle these keys
            self._list_view.setFocus()
            QApplication.sendEvent(self._list_view, event)
            return

        else:
            super().keyPressEvent(event)
