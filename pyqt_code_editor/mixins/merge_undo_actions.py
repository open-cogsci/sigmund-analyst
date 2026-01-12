from qtpy.QtCore import Qt
from qtpy.QtGui import QTextCursor


class MergeUndoActions:
    """Ensures that all changes made as part of a key press result in a 
    single edit block for undo purposes. This class should be the first
    mixin of the list.
    """
    def keyPressEvent(self, event):
        # Navigation keys that should NOT be wrapped in edit blocks. This 
        # avoids cursor glitches when navigating vertically/horizontally.
        navigation_keys = {
            Qt.Key.Key_Up, Qt.Key.Key_Down, 
            Qt.Key.Key_Left, Qt.Key.Key_Right,
            Qt.Key.Key_Home, Qt.Key.Key_End,
            Qt.Key.Key_PageUp, Qt.Key.Key_PageDown,
        }

        key = event.key()
        modifiers = event.modifiers()

        # Treat platform "command" modifier as well (Control on Windows/Linux, Meta on macOS)
        ctrl_or_meta = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
        has_ctrl_or_meta = bool(modifiers & ctrl_or_meta)
        has_shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        # Common Undo/Redo shortcuts:
        # - Undo:  Ctrl+Z / Cmd+Z
        # - Redo:  Ctrl+Shift+Z / Cmd+Shift+Z / Ctrl+Y / Cmd+Y
        is_undo = has_ctrl_or_meta and key == Qt.Key.Key_Z and not has_shift
        is_redo = has_ctrl_or_meta and (
            (key == Qt.Key.Key_Z and has_shift) or
            key == Qt.Key.Key_Y
        )

        if key in navigation_keys or is_undo or is_redo:
            # Do not wrap these in an edit block
            super().keyPressEvent(event)
            return

        # For editing keys, wrap the operation in a single edit block.
        # Use the widget's actual text cursor, not a fresh document cursor.
        cursor = self.textCursor()
        cursor.beginEditBlock()
        try:
            super().keyPressEvent(event)
        finally:
            cursor.endEditBlock()