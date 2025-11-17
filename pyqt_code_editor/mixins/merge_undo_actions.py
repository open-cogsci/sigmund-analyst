from qtpy.QtCore import Qt
from qtpy.QtGui import QTextCursor


class MergeUndoActions:
    """Ensures that all changes made as part of a key press result in a 
    single edit block for undo purposes. This class should be the first
    mixin of the list.
    """
    def keyPressEvent(self, event):
        # Navigation keys that should NOT be wrapped in edit blocks. This 
        # causes a specific issue with the cursor jumping to the start of a 
        # line when navigating vertically.
        navigation_keys = {
            Qt.Key.Key_Up, Qt.Key.Key_Down, 
            Qt.Key.Key_Left, Qt.Key.Key_Right,
            Qt.Key.Key_Home, Qt.Key.Key_End,
            Qt.Key.Key_PageUp, Qt.Key.Key_PageDown
        }
        is_navigation = (event.key() in navigation_keys and 
                         not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier))        
        if is_navigation:            
            super().keyPressEvent(event)
            return
        # Wrap all other keys (editing operations) in a single edit block to
        # unify changes into a single undo action
        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        try:
            super().keyPressEvent(event)
        finally:
            cursor.endEditBlock()