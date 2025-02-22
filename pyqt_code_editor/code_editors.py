from qtpy.QtWidgets import QPlainTextEdit
from pyqt_code_editor.mixins import Complete, PythonAutoIndent, \
    PythonAutoPair, HighlightSyntax, Zoom, LineNumber, Comment, \
    SearchReplace, Base, Check, Shortcuts, FileLink, Symbols


class PythonCodeEditor(LineNumber, Zoom, PythonAutoPair, Complete,
                       PythonAutoIndent, Comment, SearchReplace, FileLink,
                       HighlightSyntax, Check, Shortcuts, Symbols, Base,
                       QPlainTextEdit):
    pass


__all__ = ['PythonCodeEditor']
