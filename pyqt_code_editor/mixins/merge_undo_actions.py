class MergeUndoActions:
    """Ensures that all changes made as part of a key press result in a 
    single edit block for undo purposes. This class should be the first
    mixin of the list.
    """
    def keyPressEvent(self, event):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        try:
            super().keyPressEvent(event)
        finally:
            cursor.endEditBlock()
