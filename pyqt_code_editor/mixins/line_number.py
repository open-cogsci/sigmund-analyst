from qtpy.QtWidgets import QWidget, QToolTip
from qtpy.QtCore import Qt, QRect, QSize
from qtpy.QtGui import QPainter
from .. import settings


class LineNumberArea(QWidget):
    """
    A small widget placed to the left of the text editor
    that displays line numbers.
    """

    def __init__(self, editor):
        super().__init__(editor)
        self.setMouseTracking(True)
        self._editor = editor
        self.apply_stylesheet()

    def sizeHint(self):
        """
        The width is determined by the editor's
        lineNumberAreaWidth() callback.
        """
        return QSize(self._editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        """
        Delegates painting to the editor's lineNumberAreaPaintEvent method.
        """
        self._editor.lineNumberAreaPaintEvent(event)
        
    def mouseMoveEvent(self, event):
        self._editor.mouseMoveEvent(event)
        
    def apply_stylesheet(self):
        editor = self.parent()
        if editor.code_editor_colors is not None:
            self.setStyleSheet(f'''QWidget {{
                color: {editor.code_editor_colors['line-number']};
                background-color: {editor.code_editor_colors['background']};
                font: {settings.font_size}pt '{settings.font_family}';
            }}''')

class LineNumber:
    """
    Mixin class that adds a line number area to a QPlainTextEdit.
    The mixin assumes that it can access self.viewport() etc. from
    QPlainTextEdit side of the inheritance.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseTracking(True)
        # Create the line number area
        self.lineNumberArea = LineNumberArea(self)

        # Connect signals for updating
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)

        # Force an initial width update
        self.updateLineNumberAreaWidth(0)

    def lineNumberAreaSizeHint(self):
        """
        Provide a size hint for the line number area,
        used in the area itself.
        """
        return self.size()

    def lineNumberAreaWidth(self):
        """
        Compute the width needed by the line number area based on the
        number of digits in the total line count, plus some padding.
        """
        digits = len(str(max(1, self.blockCount())))
        # Add some extra space for margins
        padding = 3
        charWidth = self.fontMetrics().horizontalAdvance('9')
        return padding + self.fontMetrics().horizontalAdvance('9' * digits) + charWidth

    def updateLineNumberAreaWidth(self, _):
        """
        Adjust left margin so the editor does not paint text under the lineNumbers.
        """
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        """
        Called when the editor is scrolled or resized.
        We move/scroll the lineNumberArea accordingly, and possibly repaint.
        """
        if dy:  # simply scroll
            self.lineNumberArea.scroll(0, dy)
        else:
            # The entire area might need repainting
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

        # If resizing, update width as well
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        """
        Ensure lineNumberArea is properly resized and placed.
        """
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(
            cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()
        )
        
    def _update_line_number_rects(self):
        """
        Determines the rects around the line number area parts and the full 
        line. This is done for the entire viewport, even if we need to redraw
        only a small part of the viewport. That way, the tooltip doesn't lose
        track of where we're hovering.
        """
        self._line_number_rects = {}
        self._line_rects = {}
    
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
    
        # Starting Y coordinate of the current block
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
    
        # We'll keep iterating until we run out of visible blocks
        viewport_rect = self.viewport().rect()
        viewport_bottom = viewport_rect.bottom()
        viewport_width = viewport_rect.width()
        rect_width = self.lineNumberArea.width()
        while block.isValid() and top <= viewport_bottom:
            rect_height = self.blockBoundingRect(block).height()
            if block.isVisible():
                # We only care about block geometry if visible
                line_number_rect = QRect(0, int(top), rect_width, int(rect_height))
                self._line_number_rects[block_number] = line_number_rect
                line_rect = QRect(
                    -rect_width,
                    line_number_rect.top(),
                    viewport_width + rect_width,
                    line_number_rect.height()
                )
                self._line_rects[block_number] = line_rect
            block = block.next()
            top += rect_height
            block_number += 1      

    def lineNumberAreaPaintEvent(self, event):
        """
        Paint line numbers for each visible block, assuming self._line_number_rects
        is already populated with the correct geometry for each visible line.
        """
        self._update_line_number_rects()
        painter = QPainter(self.lineNumberArea)
        base_color = self.lineNumberArea.palette().base()
        text_color = self.lineNumberArea.palette().text().color()
        align_top_right = Qt.AlignTop | Qt.AlignRight
        painter.fillRect(event.rect(), base_color)
        for block_number, line_rect in self._line_number_rects.items():
            if line_rect.intersects(event.rect()):
                # Convert zero-based block_number to 1-based for display
                line_num = block_number + 1
                # Check if current line has a lint/check result
                annotation = self.code_editor_line_annotations.get(line_num)
                if annotation:
                    text_str = annotation['text']
                    painter.fillRect(line_rect, annotation['background_color'])
                    painter.setPen(annotation['color'])
                else:
                    text_str = str(line_num)
                    painter.setPen(text_color)
                painter.drawText(line_rect, align_top_right, text_str)
            
    def mouseMoveEvent(self, event):
        """
        Called when the mouse moves over the entire QPlainTextEdit.
        We check each line's rectangle in self._line_rects
        to see if the cursor is in that rect (covering both gutter + text).
        If so, we look up code_editor_line_annotations to see if there's
        an issue for that line, and show a tooltip. If not, hide it.
        """
        pos = event.pos()
        hovered_any_line = False
        for block_number, line_rect in self._line_rects.items():
            if line_rect.contains(pos):
                hovered_any_line = True
                line_num = block_number + 1
                annotation = self.code_editor_line_annotations.get(line_num)
                if annotation:
                    # Convert from local to global coords
                    line_number_rect = self._line_number_rects[block_number]
                    global_pos = self.mapToGlobal(line_number_rect.bottomRight())
                    QToolTip.showText(global_pos, annotation['tooltip'], self)
                else:
                    QToolTip.hideText()
                break
        if not hovered_any_line:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def update_theme(self):
        super().update_theme()
        self.lineNumberArea.apply_stylesheet()
