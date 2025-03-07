from qtpy.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, 
                            QTableView, QHeaderView, QLineEdit, QLabel, 
                            QAbstractItemView, QMenu, QAction)
from qtpy.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex
from qtpy.QtGui import QIcon, QColor, QFont, QBrush
from ..widgets import Dock


class WorkspaceModel(QAbstractTableModel):
    """Model to display variables in the workspace"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = {}  # Will store the workspace data
        self._headers = ["Name", "Type", "Value"]
        self._var_list = []  # List of variable names for easy access
        
        # Define type icons - would be properly set in a real implementation
        self._type_icons = {
            'int': None,
            'float': None,
            'str': None,
            'list': None,
            'dict': None,
            'DataFrame': None
        }
        
    def update_data(self, workspace_data):
        """Update the model with new workspace data"""
        self.beginResetModel()
        self._data = workspace_data
        self._var_list = list(workspace_data.keys())
        self.endResetModel()
        
    def rowCount(self, parent=QModelIndex()):
        return len(self._var_list)
    
    def columnCount(self, parent=QModelIndex()):
        return 3  # Name, Type, Value
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._var_list):
            return None
        
        var_name = self._var_list[index.row()]
        var_data = self._data[var_name]
        
        if role == Qt.DisplayRole:
            if index.column() == 0:
                return var_name
            elif index.column() == 1:
                return var_data['type']
            elif index.column() == 2:
                return var_data['preview']
                
        elif role == Qt.FontRole:
            font = QFont()
            # Make variable names bold
            if index.column() == 0:
                font.setBold(True)
            return font
            
        elif role == Qt.BackgroundRole:
            # Color coding based on variable type
            type_name = var_data['type']
            if 'int' in type_name or 'float' in type_name:
                return QBrush(QColor(240, 248, 255))  # Light blue for numbers
            elif 'str' in type_name:
                return QBrush(QColor(255, 248, 240))  # Light orange for strings
            elif 'list' in type_name or 'tuple' in type_name:
                return QBrush(QColor(240, 255, 240))  # Light green for sequences
            
        return None
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None

class WorkspaceExplorer(Dock):
    """Dock widget for exploring variables in the Jupyter workspace"""
    
    def __init__(self, parent=None):
        super().__init__("workspace_explorer", parent)
        self.setObjectName('workspace_explorer')
        # Main widget and layout
        self.main_widget = QWidget(self)
        self.setWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)
        
        # Search bar
        self.search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter …")
        self.search_layout.addWidget(self.search_input)
        self.layout.addLayout(self.search_layout)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Table view
        self.table_view = QTableView()
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)
        
        # Model setup
        self.model = WorkspaceModel(self)
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(-1)  # Search all columns
        
        self.table_view.setModel(self.proxy_model)
        self.layout.addWidget(self.table_view)
        
        # Connect search field
        self.search_input.textChanged.connect(self.proxy_model.setFilterFixedString)
        
        # Set up the table appearance
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)  # Name
        header.setSectionResizeMode(1, QHeaderView.Interactive)  # Type
        header.setSectionResizeMode(2, QHeaderView.Stretch)      # Value
        
        # Initial column widths
        self.table_view.setColumnWidth(0, 150)  # Name
        self.table_view.setColumnWidth(1, 100)  # Type
        
        # Enable sorting
        self.table_view.setSortingEnabled(True)
        
    def update(self, workspace_data):
        """Update the view with new workspace data"""
        self.model.update_data(workspace_data)
        # Resize rows to content
        for row in range(self.model.rowCount()):
            self.table_view.resizeRowToContents(row)
            
    def _show_context_menu(self, position):
        """Show context menu for actions on variables"""
        menu = QMenu()
        
        # Get the variable at cursor position
        index = self.table_view.indexAt(position)
        if index.isValid():
            # Map through proxy model to get the actual variable name
            source_index = self.proxy_model.mapToSource(index)
            row = source_index.row()
            var_name = self.model._var_list[row]
            
            # Add actions specific to the variable
            inspect_action = QAction(f"Inspect '{var_name}'", self)
            delete_action = QAction(f"Delete '{var_name}'", self)
            
            menu.addAction(inspect_action)
            menu.addAction(delete_action)
            
            # Show the menu
            action = menu.exec_(self.table_view.mapToGlobal(position))
            
            # Handle action selection
            # (In a real implementation, would connect to actual functionality)
            