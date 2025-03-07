from qtpy.QtCore import Signal, Qt, QTimer
from qtpy.QtGui import QTextCursor, QTextCharFormat, QColor, QKeySequence
from qtpy.QtWidgets import QShortcut, QTextEdit
from .. python_utils import extract_cells_from_code
from .. import settings
import logging

logger = logging.getLogger(__name__)


class Execute:
    """A mixin for QPlainTextEdit that signals that code should be executed.

    # Code execution

    - The shortcut for executing code is defined as
      settings.shortcut_execute_code.
    - If text is selected, the selection is expanded to to full lines. This
      ensures clean execution of partial line selections.    
    - When nothing is selected, it identifies the "cell" containing the cursor.
      This is done by extract_cells_from_code, which returns a list of cells,
      where each cell is a dict as below. The cell that contains the cursor 
      position is selected.
      
      
      {
        'description': str | None,
        'start_pos': int,
        'end_pos': int,
        'code': str
      }
      
    - Next, the selected text is executed by emitted execute_code.
    
    # File execution
    
    - The shortcut for executing a full file is defined as
      settings.shortcut_execute_file.
    """
    
    execute_code = Signal(str)
    execute_file = Signal(str)
    
    def __init__(self, *args, **kwargs):
        """Setup keyboard shortcuts for code execution."""
        # Shortcut for executing current cell or selection
        super().__init__(*args, **kwargs)
        logger.info("Initializing Execute")
        self.execute_code_shortcut = QShortcut(
            QKeySequence(settings.shortcut_execute_code), 
            self,
            context=Qt.WidgetWithChildrenShortcut
        )
        self.execute_code_shortcut.activated.connect(self.execute_selected_text)
        
        # Shortcut for executing the entire file
        self.execute_file_shortcut = QShortcut(
            QKeySequence(settings.shortcut_execute_file), 
            self,
            context=Qt.WidgetWithChildrenShortcut
        )
        self.execute_file_shortcut.activated.connect(self.execute_current_file)
        logger.info("Execute shortcuts initialized")
    
    def execute_selected_text(self):
        """Execute the selected text or the current cell if no text is selected."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            # Get the start and end positions
            start_pos = cursor.selectionStart()
            end_pos = cursor.selectionEnd()
            
            # Create a new cursor to find the start of the first line
            start_cursor = QTextCursor(self.document())
            start_cursor.setPosition(start_pos)
            start_cursor.movePosition(QTextCursor.StartOfLine)
            
            # Create a new cursor to find the end of the last line
            end_cursor = QTextCursor(self.document())
            end_cursor.setPosition(end_pos)
            if not end_cursor.atBlockEnd():
                end_cursor.movePosition(QTextCursor.EndOfLine)
            
            # Set the expanded selection
            cursor.setPosition(start_cursor.position())
            cursor.setPosition(end_cursor.position(), QTextCursor.KeepAnchor)
            self.setTextCursor(cursor)
            
            # Get the selected text and execute it
            selected_text = cursor.selectedText().replace('\u2029', '\n')  # Handle QTextEdit's line separators
            if selected_text:
                logger.info("Executing selected text (%d characters)", len(selected_text))
                self.highlight_executed_code(cursor)
                self.execute_code.emit(selected_text)
        else:
            # No selection, execute the current cell
            logger.info("No selection found, executing current cell")
            self.execute_current_cell()
    
    def execute_current_cell(self):
        """Execute the cell that contains the cursor."""
        cell = self.get_cell_at_cursor()
        if cell:
            # Create a cursor for the cell range
            cursor = QTextCursor(self.document())
            cursor.setPosition(cell['start_pos'])
            cursor.setPosition(cell['end_pos'], QTextCursor.KeepAnchor)
            
            # Highlight the cell and execute it
            logger.info("Executing cell %s-%s (%d characters)", 
                        cell['start_pos'], cell['end_pos'], len(cell['code']))
            if cell['description']:
                logger.info("Cell description: %s", cell['description'])
                
            self.highlight_executed_code(cursor)
            self.execute_code.emit(cell['code'])
        else:
            logger.info("No cell found at cursor position")
    
    def execute_current_file(self):
        """Execute the entire file."""
        text = self.toPlainText()
        if not hasattr(self, 'code_editor_file_path'):
            return
        if self.code_editor_file_path is None:
            return
        logger.info("Executing entire file (%d characters)", len(text))
        self.execute_file.emit(self.code_editor_file_path)
    
    def get_cell_at_cursor(self):
        """Get the cell that contains the current cursor position."""
        cursor_pos = self.textCursor().position()
        text = self.toPlainText()
        
        logger.info("Finding cell at cursor position %d", cursor_pos)
        cells = extract_cells_from_code(text)
        logger.info("Found %d cells in document", len(cells))
        
        # Find the cell that contains the cursor position
        for cell in cells:
            if cell['start_pos'] <= cursor_pos <= cell['end_pos']:
                logger.info("Cursor is in cell %s-%s", cell['start_pos'], cell['end_pos'])
                return cell
        
        # If no cell is found (shouldn't happen as the entire document is treated as one cell)
        # but just in case, return the entire document as a cell
        if cells:
            logger.info("No specific cell found, using first cell")
            return cells[0]
        logger.info("No cells found in document")
        return None
    
    def highlight_executed_code(self, cursor, duration=200):
        """Temporarily highlight the executed code for visual feedback.
        
        Args:
            cursor: QTextCursor with the selection to highlight
            duration: How long to show the highlight in milliseconds
        """
        # Store the current selection
        original_cursor = self.textCursor()
        
        # Apply the highlight cursor
        self.setTextCursor(cursor)
        
        # Create a highlighted format
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor(100, 100, 170, 50))  # Light blue background
        
        # Apply the format
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format = highlight_format
        self.setExtraSelections([selection])
        logger.info("Highlighted executed code (duration: %dms)", duration)
        
        # Restore the original cursor after a delay
        def restore_selection():
            self.setTextCursor(original_cursor)
            self.setExtraSelections([])
        
        QTimer.singleShot(duration, restore_selection)