from qtpy.QtWidgets import QPlainTextEdit
from pyqt_code_editor.mixins import (MergeUndoActions, Complete,
                                     HighlightSyntax, Zoom, LineNumber,
                                     Comment, SearchReplace, Base, Check,
                                     Shortcuts, FileLink, Symbols)


class Editor(MergeUndoActions, LineNumber, Zoom, Complete, Comment,
             SearchReplace, FileLink, HighlightSyntax, Check, Shortcuts,
             Symbols, Base, QPlainTextEdit):
    pass
