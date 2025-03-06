from qtpy.QtCore import Signal
from qtpy.QtWidgets import QDockWidget


class Dock(QDockWidget):

    close_requested = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.close_requested.emit()
