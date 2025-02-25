from qtpy.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QCheckBox, QLabel
)
from qtpy.QtCore import Qt, Signal
from .. import settings

    
class SearchReplaceFrame(QFrame):
    """
    A small widget containing 'Find' and optionally 'Replace' fields,
    plus checkboxes and buttons for next/prev/replace/replace all, etc.
    Hides or shows replace-related UI depending on mode.
    """
    findNextRequested = Signal()
    findPrevRequested = Signal()
    replaceOneRequested = Signal()
    replaceAllRequested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        editor = parent
        if editor.code_editor_colors is not None:
            self.setStyleSheet(f'''
            QCheckBox,
            QPushButton,
            QLineEdit,    
            QFrame {{
                color: {editor.code_editor_colors['text']};
                background-color: {editor.code_editor_colors['background']};
                font: {settings.font_size}pt '{settings.font_family}';
                padding: 8px;
            }}
            QCheckBox::indicator,
            QPushButton,
            QLineEdit,
            QFrame {{
                border-color: {editor.code_editor_colors['border']};
                border-width: 1px;
                border-style: solid;
                border-radius: 4px;
            }}
            QCheckBox::indicator:checked {{
                background-color: {editor.code_editor_colors['text']};
            }}
            QLabel {{
                border: none;
            }}
        ''')
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Find row
        findRow = QHBoxLayout()
        
        self.findLabel = QLabel("Find:", self)
        self.matchCountLabel = QLabel("0 of 0", self)
        self.findEdit = QLineEdit(self)
        self.caseBox = QCheckBox("Aa", self)
        self.caseBox.setToolTip("Case Sensitive")
        self.regexBox = QCheckBox(".*", self)
        self.regexBox.setToolTip("Use Regular Expressions")
        self.wholeWordBox = QCheckBox("\\b", self)
        self.wholeWordBox.setToolTip("Match Whole Word")
        
        self.findNextBtn = QPushButton("Next", self)
        self.findPrevBtn = QPushButton("Prev", self)
        
        findRow.addWidget(self.findLabel)
        findRow.addWidget(self.findEdit)
        findRow.addWidget(self.matchCountLabel)
        findRow.addWidget(self.caseBox)
        findRow.addWidget(self.regexBox)
        findRow.addWidget(self.wholeWordBox)
        findRow.addWidget(self.findNextBtn)
        findRow.addWidget(self.findPrevBtn)
        
        layout.addLayout(findRow)
        
        # Replace row
        replaceRow = QHBoxLayout()
        self.replaceLabel = QLabel("Replace:", self)
        self.replaceEdit = QLineEdit(self)
        self.replaceBtn = QPushButton("Replace", self)
        self.replaceAllBtn = QPushButton("Replace All", self)
        
        replaceRow.addWidget(self.replaceLabel)
        replaceRow.addWidget(self.replaceEdit)
        replaceRow.addWidget(self.replaceBtn)
        replaceRow.addWidget(self.replaceAllBtn)
        
        layout.addLayout(replaceRow)
        
        self.replaceRowWidget = replaceRow  # Keep reference to manage visibility
        
        # Connections
        self.findNextBtn.clicked.connect(self.findNextRequested)
        self.findPrevBtn.clicked.connect(self.findPrevRequested)
        self.replaceBtn.clicked.connect(self.replaceOneRequested)
        self.replaceAllBtn.clicked.connect(self.replaceAllRequested)
        
        # Default: searching only, so hide the "replace" row
        self.showSearchOnly()
    
    def showSearchOnly(self):
        # Hide replace UI
        self.replaceLabel.setVisible(False)
        self.replaceEdit.setVisible(False)
        self.replaceBtn.setVisible(False)
        self.replaceAllBtn.setVisible(False)
        self.adjustSize()
        self.resize(self.sizeHint())
    
    def showSearchReplace(self):
        # Show replace UI
        self.replaceLabel.setVisible(True)
        self.replaceEdit.setVisible(True)
        self.replaceBtn.setVisible(True)
        self.replaceAllBtn.setVisible(True)
        self.adjustSize()
        self.resize(self.sizeHint())

