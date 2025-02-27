import re
from qtpy.QtWidgets import QShortcut
from qtpy.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QAction,
    QTextCursor, QKeySequence, QTextDocument
)
from qtpy.QtCore import Qt
from .. import settings
from ..widgets.search_replace_frame import SearchReplaceFrame


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
        self.highlight_format.setBackground(QColor(settings.search_replace_background))
        self.highlight_format.setForeground(QColor(settings.search_replace_foreground))
    
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
        findShortcut = QShortcut(QKeySequence.Find, self)
        findShortcut.setContext(Qt.WidgetWithChildrenShortcut)
        findShortcut.activated.connect(self.showSearchOnly)
        
        replShortcut = QShortcut(QKeySequence.Replace, self)
        replShortcut.setContext(Qt.WidgetWithChildrenShortcut)
        replShortcut.activated.connect(self.showSearchReplace)
        
        # Hide on Escape if wanted
        self.escapeAction = QAction(self)
        self.escapeShortcut = QShortcut(QKeySequence.Cancel, self)
        self.escapeShortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.escapeShortcut.activated.connect(self.hideSearch)
        self.escapeShortcut.setEnabled(False)
        self.escapeAction.triggered.connect(self.hideSearch)
        self.escapeAction.setEnabled(False)
        self.addAction(self.escapeAction)
        
    def _showSearchReplace(self, search_only):
        # If user has single-line selection, auto-populate
        cursor = self.textCursor()
        if cursor.hasSelection():
            needle = cursor.selectedText().splitlines()            
            if len(needle) == 1:
                needle = needle[0].strip()
                self._searchFrame.findEdit.setText(needle)
            else:
                needle = self._searchFrame.findEdit.text()
            self._updateMatchLabel(needle, self._find_flags())
        
        if search_only:
            self._searchFrame.showSearchOnly()
        else:
            self._searchFrame.showSearchReplace()
        self._searchFrame.setVisible(True)
        self._searchFrame.findEdit.setFocus()
        self.updateSearchPosition()
        
        # Swap out original highlighter for the search highlighter
        self._swapToSearchHighlighter()
        self.updateHighlighter()
        self.escapeAction.setEnabled(True)
        self.escapeShortcut.setEnabled(True)         
    
    def showSearchOnly(self):
        self._showSearchReplace(search_only=True)
    
    def showSearchReplace(self):
        self._showSearchReplace(search_only=False)
    
    def hideSearch(self):
        self._searchFrame.setVisible(False)
        self.setFocus()
        self.escapeAction.setEnabled(False)
        self.escapeShortcut.setEnabled(False)
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
            
    def _find_flags(self, forward=True):
        flags = QTextDocument.FindFlag(0)
        if self._searchFrame.caseBox.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if not forward:
            flags |= QTextDocument.FindFlag.FindBackward
        if self._searchFrame.wholeWordBox.isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords
        return flags
    
    def findNext(self):
        self._find(forward=True)
    
    def findPrev(self):
        self._find(forward=False)
    
    def _find(self, forward=True):
        flags = self._find_flags(forward=forward) 
        needle = self._searchFrame.findEdit.text()
        if not needle:
            self._searchFrame.matchCountLabel.clear()
            return
        
        # 1) Attempt to find next/prev match.
        found = self.find(needle, flags)
        
        # 2) If not found, do wrap-around by jumping to start or end.
        if not found:
            cursor = self.textCursor()
            if forward:
                cursor.movePosition(QTextCursor.Start)
            else:
                cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)
            self.find(needle, flags)

        # 3) Regardless of found or wrap-around success, update label:
        self._updateMatchLabel(needle, flags)

    def _updateMatchLabel(self, needle, flags):
        """
        Counts how many total occurrences are in the document
        and which occurrence the cursor is currently on. Then sets
        "X of Y" in self._searchFrame.matchCountLabel, or clears
        it if no matches are found.
        """
        if not needle:
            self._searchFrame.matchCountLabel.clear()
            return
        
        # We'll remove any backward flag to count from top to bottom
        # so we can do a standard forward pass for counting:
        forward_flags = QTextDocument.FindFlag(flags & ~QTextDocument.FindBackward)

        # Save the user's current cursor
        saved_cursor = self.textCursor()

        # Move a fresh cursor to the start
        temp_cursor = QTextCursor(self.document())
        temp_cursor.movePosition(QTextCursor.Start)

        total_matches = 0
        current_index = 0

        # We'll store all match positions so we can see which is "current"
        found_positions = []

        # 1) Find all matches from top to bottom.
        while True:
            temp_cursor = self.document().find(needle, temp_cursor, forward_flags)
            if temp_cursor.isNull():
                break
            found_positions.append((temp_cursor.position(), temp_cursor.anchor()))
            total_matches += 1
        
        if total_matches == 0:
            # No matches at all
            self._searchFrame.matchCountLabel.setText('0 of 0')
            # Restore original cursor
            self.setTextCursor(saved_cursor)
            return
        
        # 2) Determine which match is "current" by comparing
        # our saved_cursor's position to the found positions:
        current_pos = saved_cursor.position()
        current_anchor = saved_cursor.anchor()

        for idx, (pos, anch) in enumerate(found_positions, start=1):
            if pos == current_pos and anch == current_anchor:
                current_index = idx
                break
        
        if current_index == 0:
            # Possibly just in wrap-around scenario; we can do extra logic
            # or default to 1 (the last found match).
            current_index = total_matches

        # 3) Update the label text
        self._searchFrame.matchCountLabel.setText(f"{current_index} of {total_matches}")

        # 4) Restore original cursor
        self.setTextCursor(saved_cursor)
    
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
        self.set_modified(True)
    
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
        self.set_modified(True)
    
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
        self._updateMatchLabel(self._searchFrame.findEdit.text(),
                               self._find_flags())
