from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence


class Zoom:
    """
    A mixin that implements zoom in/out with:
      - Ctrl+Plus
      - Ctrl+Minus
      - Ctrl+ScrollUp/Down
    It expects the QPlainTextEdit to have a 'code_editor_font_size'
    attribute and a 'setFont(...)' method.
    """

    def keyPressEvent(self, event):
        if (event.modifiers() & Qt.ControlModifier):
            if event.key() == Qt.Key_Plus:
                self.zoom_in()
                return
            elif event.key() == Qt.Key_Minus:
                self.zoom_out()
                return

        super().keyPressEvent(event)

    def wheelEvent(self, event):
        """
        Zoom in/out when Ctrl is pressed and the user scrolls the wheel.
        """
        if event.modifiers() & Qt.ControlModifier:
            # angleDelta().y() is typically 120 per step on many systems.
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            # Do not pass event along so normal scrolling doesn't occur
            event.accept()
        else:
            super().wheelEvent(event)

    def zoom_in(self):
        """ Increase the editor's font size by 1 point. """
        self.code_editor_font_size += 1
        self._apply_font_size()

    def zoom_out(self):
        """ Decrease the editor's font size by 1 point, down to a minimum of 1. """
        if self.code_editor_font_size > 1:
            self.code_editor_font_size -= 1
        self._apply_font_size()

    def _apply_font_size(self):
        """ Apply the current code_editor_font_size to the editor's font. """
        font = self.font()
        font.setPointSize(self.code_editor_font_size)
        self.setFont(font)
        
