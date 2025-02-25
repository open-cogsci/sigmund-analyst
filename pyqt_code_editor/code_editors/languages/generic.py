from qtpy.QtWidgets import QPlainTextEdit
from pyqt_code_editor.mixins import Complete, \
    Theme, Zoom, LineNumber, Comment, \
    AutoPair, SearchReplace, Base, Check, Shortcuts, FileLink, Symbols


class Editor(LineNumber, Zoom, Complete, AutoPair,
             Comment, SearchReplace, FileLink,
             Theme, Check, Shortcuts, Symbols, Base,
             QPlainTextEdit):
    pass
