from qtpy.QtWidgets import QPlainTextEdit
from pyqt_code_editor.mixins import Complete, PythonAutoIndent, \
    PythonAutoPair, Theme, Zoom, LineNumber, Comment, \
    SearchReplace, Base, Check, Shortcuts, FileLink, Symbols


class Editor(LineNumber, Zoom, PythonAutoPair, Complete,
             PythonAutoIndent, Comment, SearchReplace, FileLink,
             Theme, Check, Shortcuts, Symbols, Base,
             QPlainTextEdit):
                 
    code_editor_language = 'python'
