from qtpy.QtWidgets import QPlainTextEdit
from pyqt_code_editor.mixins import (MergeUndoActions, Complete,
                                     HighlightSyntax, Zoom, LineNumber,
                                     SearchReplace, Base, Check, Shortcuts,
                                     FileLink)


class Editor(MergeUndoActions, LineNumber, Zoom, Complete, SearchReplace,
             FileLink, HighlightSyntax, Check, Shortcuts, Base,
             QPlainTextEdit):
    pass
