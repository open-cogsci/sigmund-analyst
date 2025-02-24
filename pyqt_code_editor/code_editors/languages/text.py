from qtpy.QtWidgets import QPlainTextEdit
from pyqt_code_editor.mixins import Complete, \
    HighlightSyntax, Zoom, LineNumber, \
    SearchReplace, Base, Check, Shortcuts, FileLink, Symbols


class Editor(LineNumber, Zoom, Complete, SearchReplace, FileLink,
             HighlightSyntax, Check, Shortcuts, Base, QPlainTextEdit):
    pass
