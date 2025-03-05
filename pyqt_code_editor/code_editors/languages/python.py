from qtpy.QtWidgets import QPlainTextEdit
from pyqt_code_editor.mixins import Complete, PythonAutoIndent, \
    PythonAutoPair, Theme, Zoom, LineNumber, Comment, \
    SearchReplace, Base, Check, Shortcuts, FileLink, Symbols, \
    SmartBackspaceDelete, Execute


class Editor(LineNumber, Zoom, SmartBackspaceDelete, PythonAutoPair, Complete,
             PythonAutoIndent, Comment, SearchReplace, FileLink, Execute,
             Theme, Check, Shortcuts, Symbols, Base,
             QPlainTextEdit):
                 
    code_editor_language = 'python'
