import re
from qtpy.QtWidgets import (
    QPlainTextEdit, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QCheckBox, QLabel, QShortcut, QApplication
)
from qtpy.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QAction,
    QCursor, QTextCursor, QKeySequence, QTextDocument
)
from qtpy.QtCore import Qt, QRect, Signal, QRegularExpression, QEvent

class SearchReplaceHighlighter(QSyntaxHighlighter):
    """
    Simple syntax highlighter that highlights all matches of a given pattern.
    Updated whenever the pattern or text changes.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pattern = ""
        self._use_regex = False
        self._case_sensitive = False
        self._whole_word = False
        
        # Highlight style
        self.highlight_format = QTextCharFormat()
        self.highlight_format.setBackground(QColor("#fdff74"))  # light yellow
        self.highlight_format.setForeground(QColor("#000000"))
    
    def setSearchOptions(self, pattern, use_regex, case_sensitive, whole_word):
        self._pattern = pattern
        self._use_regex = use_regex
        self._case_sensitive = case_sensitive
        self._whole_word = whole_word
        self.rehighlight()  # Trigger a re-scan
    
    def highlightBlock(self, text):
        if not self._pattern:
            return
        
        # Build the pattern
        pattern = self._pattern
        flags = 0 if self._case_sensitive else re.IGNORECASE
    
        if self._use_regex:
            # If whole_word is asked for, add \b on both sides (can be tricky with punctuation).
            if self._whole_word:
                pattern = rf"\b{pattern}\b"
            try:
                regex = re.compile(pattern, flags)
            except re.error:
                return  # invalid regex, just skip
        else:
            # Escape user text if not in regex mode
            pattern = re.escape(pattern)
            if self._whole_word:
                pattern = rf"\b{pattern}\b"
            regex = re.compile(pattern, flags)
        
        for match in regex.finditer(text):
            start = match.start()
            length = match.end() - match.start()
            self.setFormat(start, length, self.highlight_format)


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
                font: {editor.code_editor_font_size}pt '{editor.code_editor_font_family}';
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


class SearchReplace:
    """
    A mixin for QPlainTextEdit that floats a search/replace widget
    at the top-right corner, highlights all matches, and supports
    next/prev/replace operations. Automatically uses a single-line
    selection as the search needle if available.

    This version swaps out your 'original' syntax highlighter with
    our search highlighter while the search widget is visible, so only
    one QSyntaxHighlighter is attached at a time.
    """
    
    def __init__(self, *args, **kwargs):
        """
        The derived editor class must:
          1) Inherit from QPlainTextEdit + SearchReplace
          2) Call super().__init__() properly.
        """
        super().__init__(*args, **kwargs)
        self._originalHighlighter = None  # We'll store your existing syntax highlighter here
        self._searchHighlighter = SearchReplaceHighlighter(None)  # We'll attach/detach dynamically
        
        self.setupSearchReplace()
    
    def setSyntaxHighlighter(self, highlighter):
        """
        Call this to register your normal syntax highlighter.
        We'll attach/detach it as needed.
        """
        self._originalHighlighter = highlighter
        if highlighter:
            highlighter.setDocument(self.document())
    
    def setupSearchReplace(self):
        """
        Call this once in your QPlainTextEdit subclass's __init__ 
        """
        # Create the search/replace frame
        self._searchFrame = SearchReplaceFrame(self)
        self._searchFrame.setVisible(False)
        
        # Connect signals
        self._searchFrame.findNextRequested.connect(self.findNext)
        self._searchFrame.findPrevRequested.connect(self.findPrev)
        self._searchFrame.replaceOneRequested.connect(self.replaceOne)
        self._searchFrame.replaceAllRequested.connect(self.replaceAll)
        
        # Whenever user changes the find text or toggles checkboxes, re-highlight
        self._searchFrame.findEdit.textChanged.connect(self.updateHighlighter)
        self._searchFrame.caseBox.toggled.connect(self.updateHighlighter)
        self._searchFrame.regexBox.toggled.connect(self.updateHighlighter)
        self._searchFrame.wholeWordBox.toggled.connect(self.updateHighlighter)
        
        # Shortcuts
        findShortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        findShortcut.activated.connect(self.showSearchOnly)
        
        replShortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        replShortcut.activated.connect(self.showSearchReplace)
        
        # Hide on Escape if wanted
        self.escapeAction = QAction(self)
        self.escapeAction.setShortcut(QKeySequence("Escape"))
        self.escapeAction.triggered.connect(self.hideSearch)
        self.escapeAction.setEnabled(False)
        self.addAction(self.escapeAction)
    
    def showSearchOnly(self):
        # If user has single-line selection, auto-populate
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            if "\n" not in text:
                self._searchFrame.findEdit.setText(text)
        
        self._searchFrame.showSearchOnly()
        self._searchFrame.setVisible(True)
        self._searchFrame.findEdit.setFocus()
        self.updateSearchPosition()
        
        # Swap out original highlighter for the search highlighter
        self._swapToSearchHighlighter()
        self.updateHighlighter()
        self.escapeAction.setEnabled(True)
    
    def showSearchReplace(self):
        # If user has single-line selection, auto-populate
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            if "\n" not in text:
                self._searchFrame.findEdit.setText(text)
        
        self._searchFrame.showSearchReplace()
        self._searchFrame.setVisible(True)
        self._searchFrame.findEdit.setFocus()
        self.updateSearchPosition()
        
        # Swap out original highlighter for the search highlighter
        self._swapToSearchHighlighter()
        self.updateHighlighter()
        self.escapeAction.setEnabled(True)
    
    def hideSearch(self):
        self._searchFrame.setVisible(False)
        self.setFocus()
        self.escapeAction.setEnabled(False)
        # Revert to original highlighter
        self._revertToOriginalHighlighter()
    
    def resizeEvent(self, event):
        """ Overridden to keep the search frame pinned top-right. """
        super().resizeEvent(event)
        self.updateSearchPosition()
    
    def updateSearchPosition(self):
        if self._searchFrame.isVisible():
            # Pin to top-right with some margin
            margin = 20
            frame_width = self._searchFrame.width()
            self._searchFrame.move(self.width() - frame_width - margin, margin)
    
    def _swapToSearchHighlighter(self):
        """
        Temporarily remove the original syntax highlighter
        and attach the search highlighter.
        """
        if self._originalHighlighter:
            self._originalHighlighter.setDocument(None)
        self._searchHighlighter.setDocument(self.document())
    
    def _revertToOriginalHighlighter(self):
        """
        Detach the search highlighter and restore the original highlighter.
        """
        self._searchHighlighter.setDocument(None)
        if self._originalHighlighter:
            self._originalHighlighter.setDocument(self.document())
    
    def findNext(self):
        self._find(forward=True)
    
    def findPrev(self):
        self._find(forward=False)
    
    def _find(self, forward=True):
        flags = QTextDocument.FindFlag(0)
        if self._searchFrame.caseBox.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if not forward:
            flags |= QTextDocument.FindFlag.FindBackward
        if self._searchFrame.wholeWordBox.isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords
        
        needle = self._searchFrame.findEdit.text()
        if not needle:
            return
        
        # Wrap-around approach
        found = self.find(needle, QTextDocument.FindFlag(flags))
        if not found:
            cursor = self.textCursor()
            if forward:
                cursor.movePosition(QTextCursor.Start)
            else:
                cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)
            self.find(needle, flags)
    
    def replaceOne(self):
        needle = self._searchFrame.findEdit.text()
        if not needle:
            return
        
        cursor = self.textCursor()
        if cursor.hasSelection():
            # Optionally verify the selected text is the current match. We'll skip that check here.
            replacement_text = self._searchFrame.replaceEdit.text()
            cursor.insertText(replacement_text)
            self.setTextCursor(cursor)
        self.findNext()
        self.updateHighlighter()
    
    def replaceAll(self):
        needle = self._searchFrame.findEdit.text()
        if not needle:
            return
        
        replacement = self._searchFrame.replaceEdit.text()
        
        # Save cursor
        saved_cursor = self.textCursor()
        text = self.toPlainText()
        
        # Build regex pattern
        flags = 0 if self._searchFrame.caseBox.isChecked() else re.IGNORECASE
        patt = needle
        if not self._searchFrame.regexBox.isChecked():
            patt = re.escape(patt)
        if self._searchFrame.wholeWordBox.isChecked():
            patt = rf"\b{patt}\b"
        
        try:
            compiled = re.compile(patt, flags)
        except re.error:
            return
        
        new_text, num_replacements = compiled.subn(replacement, text)
        self.setPlainText(new_text)
        
        # After replace all, set the needle to the replacement text
        self._searchFrame.findEdit.setText(replacement)
        
        # Restore cursor
        self.setTextCursor(saved_cursor)
        self.updateHighlighter()
    
    def updateHighlighter(self):
        # When search widget is hidden, the search highlighter won't be attached
        # So only do this if the widget is visible
        if not self._searchFrame.isVisible():
            return
        
        find_text = self._searchFrame.findEdit.text()
        use_regex = self._searchFrame.regexBox.isChecked()
        case_sensitive = self._searchFrame.caseBox.isChecked()
        whole_word = self._searchFrame.wholeWordBox.isChecked()
        
        self._searchHighlighter.setSearchOptions(
            find_text, use_regex, case_sensitive, whole_word
        )
        
        # Count total matches to enable/disable buttons
        match_count = 0
        if find_text:
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = find_text
            if not use_regex:
                pattern = re.escape(pattern)
            if whole_word:
                pattern = rf"\b{pattern}\b"
            try:
                compiled = re.compile(pattern, flags)
                match_count = len(compiled.findall(self.toPlainText()))
            except re.error:
                match_count = 0
        
        # Enable/disable buttons based on matches
        has_matches = (match_count > 0)
        self._searchFrame.findNextBtn.setEnabled(has_matches)
        self._searchFrame.findPrevBtn.setEnabled(has_matches)
        self._searchFrame.replaceBtn.setEnabled(has_matches)
        self._searchFrame.replaceAllBtn.setEnabled(has_matches)
