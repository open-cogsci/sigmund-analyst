from qtpy.QtWidgets import QPlainTextEdit
from pyqt_code_editor.mixins import Complete, \
    HighlightSyntax, Zoom, LineNumber, Comment, \
    AutoPair, SearchReplace, Base, Check, Shortcuts, FileLink, Symbols


class Editor(LineNumber, Zoom, Complete, AutoPair,
             Comment, SearchReplace, FileLink,
             HighlightSyntax, Check, Shortcuts, Symbols, Base,
             QPlainTextEdit):
    pass
