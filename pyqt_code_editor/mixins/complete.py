import os
import sys
import logging
from qtpy.QtCore import QTimer, Qt
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import QApplication
from ..widgets.completion_popup import CompletionPopup
from ..widgets.calltip_widget import CalltipWidget
from ..environment_manager import environment_manager
from .. import settings
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class Complete:
    """
    A mixin providing code-completion logic, designed to be paired with
    a QPlainTextEdit (or derived) class in multiple inheritance.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("Initializing Complete")

        self._cm_full_completion_timer = QTimer(self)
        self._cm_full_completion_timer.setSingleShot(True)
        self._cm_full_completion_timer.setInterval(settings.full_completion_delay)
        self._cm_full_completion_timer.timeout.connect(self._cm_full_completion_dispatch)
        
        self._cm_hide_completion_timer = QTimer(self)
        self._cm_hide_completion_timer.setSingleShot(True)
        self._cm_hide_completion_timer.setInterval(settings.hide_completion_delay)
        self._cm_hide_completion_timer.timeout.connect(self._cm_hide_completion_dispatch)
        
        self._ignore_next_completion = False

        # Track the cursor position when a request was made
        self._cm_requested_cursor_pos = None
        self._cm_requested_calltip_cursor_pos = None

        # Create the popup for completions
        self._cm_completion_popup = CompletionPopup(self)

        # Create (but keep hidden) our persistent calltip widget
        self._cm_calltip_widget = CalltipWidget(self)
        self._cm_calltip_widget.hide()
        self._cm_paren_prefix = None
        logger.info("Complete initialized.")

    def _update_paren_prefix_cache(self):
        """
        Build a prefix array self._cm_paren_prefix so that
        self._cm_paren_prefix[i] = net # of '(' minus ')' from the start of the text up to (but not including) index i.
        
        Then, for a cursor position p, if self._cm_paren_prefix[p] > 0, we know there's at least one unmatched '('.
        """
        text = self.toPlainText()
        prefix = [0] * (len(text) + 1)  # prefix[0] = 0, prefix[i] for i>0 is the balance up to i-1
        balance = 0
        for i, ch in enumerate(text):
            if ch == '(':
                balance += 1
            elif ch == ')':
                balance -= 1
            prefix[i + 1] = balance
        self._cm_paren_prefix = prefix
    
    def _cursor_follows_unclosed_paren(self):
        """
        Use the prefix cache to quickly check if the current cursor
        is inside an unmatched '(' context.
        """
        
        pos = self.textCursor().position()
        if self._cm_paren_prefix is None or pos >= len(self._cm_paren_prefix):
            self._update_paren_prefix_cache()
        if pos >= len(self._cm_paren_prefix):
            return False
        return self._cm_paren_prefix[pos] > 0
    
    def _is_navigation_key(self, event):
        """Return True if event is a navigation key (arrow/home/end/page)."""
        nav_keys = {
            Qt.Key_Up, Qt.Key_Down, Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp,
            Qt.Key_PageDown
        }
        return event.key() in nav_keys
    
    def mousePressEvent(self, event):
        """Make sure the calltip doesn't stay open when we navigate away with
        the mouse.
        """
        super().mousePressEvent(event)
        self._cm_hide_and_recheck_calltip_if_unclosed()
        self._cm_completion_popup.hide()
        
    def wheelEvent(self, event):
        """Make sure the calltip doesn't stay open when we scroll the viewport.
        """
        super().wheelEvent(event)
        self._cm_hide_calltip()
        self._cm_completion_popup.hide()
        
    def focusOutEvent(self, event):
        """Make sure the calltip doesn't stay open when the widget loses focus.
        """
        super().focusOutEvent(event)
        self._cm_hide_calltip()
        self._cm_completion_popup.hide()
    
    def keyPressEvent(self, event):
        """
        Updated logic to prevent completion on arrow keys:
          • We skip calling self._cm_full_completion_timer.start() if the user pressed a nav key.
        """
        # When a key is pressed, we want to stop the full complete request. In case the
        # request is already sent, we also set a flag to ignore the result when it comes
        # in
        if self._cm_full_completion_timer.isActive():
            self._cm_full_completion_timer.stop()
        self._ignore_next_completion = True
        # Now process the key press
        typed_char = event.text()
        old_pos = self.textCursor().position()  # remember cursor pos before super()
        # 1) If the popup is visible, handle completion navigation or acceptance.
        if self._cm_completion_popup.isVisible():
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab):
                item = self._cm_completion_popup.currentItem()
                if item is not None:
                    self._cm_completion_popup.insert_completion(item)
                self._cm_completion_popup.hide()
                event.accept()
                return
            elif event.key() == Qt.Key_Up:
                row = self._cm_completion_popup.currentRow()
                self._cm_completion_popup.setCurrentRow(max(0, row - 1))
                event.accept()
                return
            elif event.key() == Qt.Key_Down:
                row = self._cm_completion_popup.currentRow()
                self._cm_completion_popup.setCurrentRow(min(self._cm_completion_popup.count() - 1, row + 1))
                event.accept()
                return
            elif event.key() == Qt.Key_Escape:
                self._cm_completion_popup.hide()
                event.accept()
                return
            # Otherwise, fall through to normal handling below

        # We hide the completion timer with a short delay. This is to make sure
        # that the completion popup doesn't linger after key presses.            
        if not self._cm_hide_completion_timer.isActive():
            self._cm_hide_completion_timer.start()
    
        # 2) Detect Ctrl+Space => multiline completion
        if (event.key() == Qt.Key_Space) and (event.modifiers() & Qt.ControlModifier):
            logger.info("Detected Ctrl+Space => multiline completion.")
            self._cm_request_completion(multiline=True)
            event.accept()
            return
    
        # 3) Check left/right arrow:
        is_left = (event.key() == Qt.Key_Left)
        is_right = (event.key() == Qt.Key_Right)
        if is_left or is_right:
            super().keyPressEvent(event)
            new_pos = self.textCursor().position()
    
            # If we moved left and jumped over '(' => hide & re-check
            if is_left and (old_pos - new_pos == 1):
                text = self.toPlainText()
                if 0 <= new_pos < len(text) and text[new_pos] in '()':
                    self._cm_hide_and_recheck_calltip_if_unclosed()
                return
    
            # If we moved right and jumped over ')' => hide & re-check
            if is_right and (new_pos - old_pos == 1):
                text = self.toPlainText()
                if 0 <= old_pos < len(text) and text[old_pos] in '()':
                    self._cm_hide_and_recheck_calltip_if_unclosed()
                return
            return
    
        # 4) If user pressed a navigation key (Home, End, PgUp, etc.), hide calltip and re-check
        if self._is_navigation_key(event):
            super().keyPressEvent(event)
            self._cm_hide_and_recheck_calltip_if_unclosed()
            return
    
        # 5) If user typed ")", hide calltip immediately
        if typed_char == ')':
            super().keyPressEvent(event)
            self._update_paren_prefix_cache()
            logger.info("User typed ')' => hiding calltip.")
            self._cm_hide_calltip()
            # Possibly also finalize arguments => request normal completion
            self._cm_full_completion_timer.start()
            return
    
        # 6) Detect if backspace removes '(' => hide calltip
        backspace_removing_open_paren = False
        if event.key() == Qt.Key_Backspace:
            cursor = self.textCursor()
            if cursor.position() > 0:
                cursor.movePosition(cursor.Left, cursor.KeepAnchor)
                if cursor.selectedText() == '(':
                    backspace_removing_open_paren = True
    
        # Let the editor insert or remove the character normally
        super().keyPressEvent(event)
    
        # 7) Update the paren cache after text changed
        self._update_paren_prefix_cache()
    
        # 8) If user typed "(", request a calltip
        if typed_char == '(':
            logger.info("User typed '(' => requesting calltip.")
            self._cm_request_calltip()
    
        # 9) If we removed an "(", hide calltip
        if backspace_removing_open_paren:
            logger.info("User removed '(' => hiding calltip.")
            self._cm_hide_calltip()
    
        # 10) Hide/keep the popup based on typed_char
        if typed_char:
            if typed_char.isalnum() or typed_char in ('_', '.') or event.key() == Qt.Key_Backspace:
                logger.info(f"User typed identifier-like char {typed_char!r}; keeping popup open (if visible).")
                # Only start the debounce timer if we have an actual typed character,
                # so pressing arrow/navigation keys never triggers completion.
                self._cm_request_completion()
            else:
                logger.info(f"User typed non-identifier char {typed_char!r}; hiding popup.")
                self._cm_completion_popup.hide()
    
        else:
            logger.info("No typed_char => not starting debounce timer.")
    
    
    def _cm_hide_and_recheck_calltip_if_unclosed(self):
        """
        Helper to hide the calltip if currently visible, then re-request it if
        we still have an unmatched '(' at the cursor.
        """
        if self._cm_calltip_widget.isVisible():
            self._cm_hide_calltip()
        if self._cursor_follows_unclosed_paren():
            self._cm_request_calltip()
    
    
    def _cm_full_completion_dispatch(self):
        """
        Called by the debounce timer to request a full complete, which can include
        more time-consuming completions, such as AI-generated completions.
        """
        self._cm_request_completion(multiline=False, full=True)
        
    def _cm_hide_completion_dispatch(self):
        """
        Called by the debounce timer to hide a completion with a short delay after
        a key press. This is to avoid completions from remaining visible after the
        cursor has moved, in case no completion came in to hide or replace it.
        """
        if self._cm_completion_popup.isVisible():
            self._cm_completion_popup.hide()

    def _cm_request_completion(self, multiline=False, full=False):
        """Send a completion request if one is not already in progress."""
        self._ignore_next_completion = False
        code = self.toPlainText()
        cursor_pos = self.textCursor().position()
        logger.info("Requesting completions at cursor_pos=%d, multiline=%s", cursor_pos, multiline)

        self._cm_requested_cursor_pos = cursor_pos
        self.send_worker_request(action='complete', code=code,
                                 cursor_pos=cursor_pos, full=full,
                                 multiline=multiline,
                                 path=self.code_editor_file_path,
                                 language=self.code_editor_language,
                                 env_path=environment_manager.path)

    def _cm_request_calltip(self):
        """Send a calltip request."""
        code = self.toPlainText()
        cursor_pos = self.textCursor().position()
        self._cm_requested_calltip_cursor_pos = cursor_pos        
        logger.info("Requesting calltip at cursor_pos=%d", cursor_pos)
        self.send_worker_request(action='calltip', code=code,
                                 cursor_pos=cursor_pos,
                                 path=self.code_editor_file_path,
                                 language=self.code_editor_language,
                                 env_path=environment_manager.path)

    def _cm_hide_calltip(self):
        """Hide the calltip widget."""
        self._cm_calltip_widget.hide()

    def handle_worker_result(self, action, result):
        """Check for completion or calltip results from the external worker."""
        super().handle_worker_result(action, result)
        if action == 'complete':
            logger.info("Handling 'complete' action with result")
            self._cm_complete(**result)
        elif action == 'calltip':
            logger.info("Handling 'calltip' action with result")
            self._cm_calltip(**result)
            
    def _cm_insert_completion(self, completion):
        """
        This function is called when a completion fragment is selected
        in a code editor that is based on a QPlainTextEdit. The completion
        should be inserted at the cursor position, but there are a few
        things to consider:

        If the completion overlaps with the text that follows the cursor,
        this trailing text should be removed to avoid duplication.

        For example, in the situation below, the ')' should not be duplicated.
        The | indicates the cursor position.

        Text: print('Hello|')
        Completion: world')
        Result: print('Hello world')

        The same holds for the previous text:

        Text: print('Hello|')
        Completion: Hello world')
        Result: print('Hello world')

        Now, we also want to remove any partial overlap on the left side
        (i.e., if the user has already typed part of the completion that
        appears at the beginning of completion). For instance, if the
        user has typed "Hell" and the completion is "Hello world')", we
        don't want to insert "Hell" again.
        
        An exception is when there is exactly one character of overlap on
        the left. This can happen for genuine completions like "Hel" and
        "lo", where the double "l" should be preserved.

        This function handles both directions:
        1. Finds overlap at the end of the text before the cursor.
        2. Finds overlap at the beginning of the text after the cursor.
        """
        cursor = self.textCursor()
        doc_text = self.toPlainText()
        current_pos = cursor.position()

        # 1) Handle left-side overlap:
        #    If part of the completion is already typed before the cursor,
        #    we will skip that part of the completion.
        before_text = doc_text[max(0, current_pos - len(completion)): current_pos]
        left_overlap_size = 0
        max_check_left = min(len(before_text), len(completion))
        # Find the largest suffix of 'before_text' that matches
        # the prefix of 'completion'
        for i in range(max_check_left, 0, -1):
            if before_text[-i:] == completion[:i]:
                left_overlap_size = i
                break
        # Captures special case of exactly 1 character of left overlap, which
        # can reflect words with double letters, but it doesn't need to. To
        # decide whether the overlap needs to be removed we check whether the
        # stripped version exists in the text. If so, we use that, if not,
        # we assume that the doubling is intended.
        #
        # def aabb(): pass
        # a| completion is 'abb' overlap = 0
        #
        # def abb(): pass
        # a| completion is 'abb' overlap = 1        
        if left_overlap_size == 1:
            # Get the index of the last character in before_text that is
            # alphanumeric or underscore
            last_symbol_index = -1
            while -last_symbol_index <= len(before_text) and \
                    (before_text[last_symbol_index].isalnum() or
                     before_text[last_symbol_index] == '_'):
                last_symbol_index -= 1
            last_symbol_index += 1
            symbol_before = before_text[last_symbol_index:]
            # Get the index of the first character in completion that is
            # alphanumeric or underscore
            last_symbol_index = 0
            while last_symbol_index < len(completion) and \
                    (completion[last_symbol_index].isalnum() or
                     completion[last_symbol_index] == '_'):
                last_symbol_index += 1
            symbol_after = completion[:last_symbol_index]
            symbol = symbol_before + symbol_after
            if symbol in doc_text:
                left_overlap_size = 0
                logger.info(f'{symbol} exists in text, keeping overlap')                
            else:
                logger.info(f'{symbol} does not exists in text, stripping overlap')                
        # Create a new completion without what's already typed
        new_completion = completion[left_overlap_size:]

        # 2) Handle right-side overlap:
        #    If the text immediately after the cursor duplicates
        #    the new_completion, remove that overlap from the document.
        after_text = doc_text[current_pos : current_pos + len(new_completion)]
        right_overlap_size = 0
        max_check_right = min(len(new_completion), len(after_text))
        # Find the largest prefix of 'after_text' that matches
        # the suffix of 'new_completion'
        for i in range(max_check_right, 0, -1):
            if new_completion[-i:] == after_text[:i]:
                right_overlap_size = i
                break

        cursor.beginEditBlock()
        if right_overlap_size > 0:
            # Remove the overlapping segment from the document
            cursor.setPosition(current_pos, QTextCursor.MoveAnchor)
            cursor.setPosition(current_pos + right_overlap_size,
                               QTextCursor.KeepAnchor)
            cursor.removeSelectedText()

        # 3) Insert the final completion text
        cursor.insertText(new_completion)
        cursor.endEditBlock()
        self.setTextCursor(cursor)        

    def _cm_complete(self, completions, cursor_pos, multiline, full):
        """Handle completion results from the worker."""
        if self._ignore_next_completion:
            logger.info("Ignoring completion results.")
            self._ignore_next_completion = False
            return
        # Discard if cursor changed since the request
        if cursor_pos != self.textCursor().position():
            return

        if not completions:
            # Even there are no completions, we still want to get full completions
            if not multiline and not full:
                self._cm_full_completion_timer.start()
            self._cm_completion_popup.hide()            

        if multiline:
            if not completions:
                return
            logger.info("Inserting first multiline completion: '%s'", completions[0])
            completion_text = completions[0]['completion']
            cursor = self.textCursor()
            start = cursor.position()
            cursor.insertText(completion_text)
            end = cursor.position()
            # Highlight what was inserted
            cursor.setPosition(start, QTextCursor.MoveAnchor)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            self.setTextCursor(cursor)
        else:
            logger.info("Showing completion popup with %d completions.", len(completions))
            # stop hide completion timer if it is active
            if self._cm_hide_completion_timer.isActive():
                self._cm_hide_completion_timer.stop()
            # show completions
            self._cm_completion_popup.show_completions(completions)
            if not full:
                self._cm_full_completion_timer.start()

    def _cm_calltip(self, signatures, cursor_pos):
        """
        Called when the worker returns calltip signature info.
        """
        # Discard if cursor changed since the request
        if cursor_pos != self.textCursor().position():
            logger.info(
                "Discarding calltip because cursor changed (old=%d, new=%d).",
                cursor_pos, self.textCursor().position())
            return

        if not signatures:
            logger.info("No signature info returned.")
            return

        text = "\n\n".join(signatures)
        self._cm_show_calltip(text)

    def _cm_show_calltip(self, text):
        """
        Display the calltip as a small persistent widget below the cursor line,
        horizontally aligned with the cursor, so it doesn't obscure typed text.
        If there's not enough space below, show it above the cursor instead.
        """
        if self._cm_calltip_widget.isVisible():
            logger.info("Calltip widget already visible, updating text.")
            self._cm_calltip_widget.setText(text)
            return

        logger.info("Displaying calltip widget.")
        self._cm_calltip_widget.setText(text)

        # QPlainTextEdit provides cursorRect(), returning the bounding rect of
        # the text cursor relative to the editor's viewport.
        cr = self.cursorRect()

        # Get the screen geometry to check boundaries
        screen = QApplication.primaryScreen()
        screen_rect = screen.availableGeometry()
    
        # Calculate the calltip size
        self._cm_calltip_widget.adjustSize()
        calltip_height = self._cm_calltip_widget.height()
    
        # Convert cursor bottom-left to global coordinates
        global_bottom_left = self.mapToGlobal(cr.bottomLeft())
        global_bottom_left.setX(global_bottom_left.x() + self.viewportMargins().left())
    
        # Check if calltip would fit below the cursor
        if global_bottom_left.y() + calltip_height > screen_rect.bottom():
            # Not enough space below, show above cursor instead
            global_pos = self.mapToGlobal(cr.topRight())
            global_pos.setX(global_pos.x() + self.viewportMargins().left())
            global_pos.setY(global_pos.y() - calltip_height)
            logger.info("Positioning calltip above cursor due to screen boundaries.")
        else:
            # Enough space below, use bottom-left position
            global_pos = global_bottom_left
            logger.info("Positioning calltip below cursor.")
    
        self._cm_calltip_widget.move(global_pos)
        self._cm_calltip_widget.show()

    def closeEvent(self, event):
        """
        Ensure the worker shuts down. Then let the next class in the MRO
        handle the close event (which is typically QPlainTextEdit).
        """
        logger.info("Closing editor, shutting down completion worker.")
        self._cm_request_queue.put({'action': 'quit'})
        self._cm_worker_process.join()
        super().closeEvent(event)
        logger.info("Editor closed, worker process joined.")

    def update_theme(self):
        super().update_theme()
        self._cm_calltip_widget.apply_stylesheet()

    def _current_environment(self):
        return os.environ.get('SIGMUND_PYENV', sys.executable)
