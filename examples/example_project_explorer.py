import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pyqt_code_editor import watchdog
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget
from qtpy.QtCore import QDir
from pyqt_code_editor.components.project_explorer import ProjectExplorer


class DummyEditorPanel:
    
    def open_file(self, *args, **kwargs):
        pass


class MainWindow(QWidget):
    def __init__(self, path=None):
        super().__init__()
        self.setWindowTitle("PyQtCodeEditor")
        layout = QVBoxLayout()        
        project_explorer = ProjectExplorer(DummyEditorPanel(), root_path=path)
        layout.addWidget(project_explorer)
        self.setLayout(layout)

    def closeEvent(self, event):
        watchdog.shutdown()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    path = None
    if len(sys.argv) > 1:
        path = sys.argv[1]    
    else:
        path = QDir.currentPath()
    win = MainWindow(path)
    win.show()
    sys.exit(app.exec_())
