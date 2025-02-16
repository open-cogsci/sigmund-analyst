import sys
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget, QPlainTextEdit
from pyqt_code_editor_mixins.completion_mixin import CompletionMixin


class CodeEditor(CompletionMixin, QPlainTextEdit):
    def __init__(self, parent=None, language='text', path=None):
        QPlainTextEdit.__init__(self, parent)
        CompletionMixin.__init__(self, language=language, file_path=path)
        

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Code Editor with External Completion")
        layout = QVBoxLayout()
        self.editor = CodeEditor(language='python')
        self.editor.setPlainText('''from matplotlib import pyplot as plt
fig = plt.figure(figsize=(6, 6))
''')
        layout.addWidget(self.editor)
        self.setLayout(layout)


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
