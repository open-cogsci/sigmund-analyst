from qtpy.QtWidgets import QPlainTextEdit
from pyqt_code_editor.mixins import (MergeUndoActions, Complete, Theme, Zoom,
                                     LineNumber, Comment, AutoIndent,
                                     AutoPair, SearchReplace, Base, Check,
                                     Shortcuts, FileLink, Symbols,
                                     HighlightMatchingBrackets)


class Editor(MergeUndoActions, LineNumber, Zoom, Complete, AutoIndent,
             AutoPair, Comment, SearchReplace, FileLink, Theme, Check,
             Shortcuts, HighlightMatchingBrackets, Symbols, Base,
             QPlainTextEdit):
    pass
