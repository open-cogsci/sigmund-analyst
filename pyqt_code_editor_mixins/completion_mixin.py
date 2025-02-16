import logging; logging.basicConfig(level=logging.INFO, force=True)
import multiprocessing
from queue import Empty
from qtpy.QtCore import QTimer, Qt, QPoint
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import QFrame, QLabel, QVBoxLayout
from .completion_popup import CompletionPopup
from .calltip_widget import CalltipWidget
from .completion_worker import completion_worker

logger = logging.getLogger(__name__)

class CompletionMixin:
    """
    A mixin providing code-completion logic, designed to be paired with
    a QPlainTextEdit (or derived) class in multiple inheritance.

    Usage:
        class MyEditor(CompletionMixin, QPlainTextEdit):
            def __init__(self, parent=None, language='text', path=None):
                QPlainTextEdit.__init__(self, parent)
                CompletionMixin.__init__(self, language=language, file_path=path)
    """

    def __init__(self, language='text', file_path=None):
        """
        DON'T call super().__init__() here, because we don't want to collide
        with the QPlainTextEdit constructor in multiple inheritance.
        Instead, the final class initializes QPlainTextEdit first, then calls
        CompletionMixin.__init__().
        """
        logger.info("Initializing CompletionMixin with language=%s, file_path=%s", language, file_path)

        # Store the file path and language
        self._cm_file_path = file_path
        self._cm_language = language.lower() if language else 'text'

        # Worker process + queues
        self._cm_request_queue = multiprocessing.Queue()
        self._cm_result_queue = multiprocessing.Queue()
        self._cm_worker_process = multiprocessing.Process(
            target=completion_worker,
            args=(self._cm_request_queue, self._cm_result_queue),
        )
        logger.info("Starting completion worker process.")
        self._cm_worker_process.start()

        # Debounce timer (100 ms)
        self._cm_debounce_timer = QTimer(self)
        self._cm_debounce_timer.setSingleShot(True)
        self._cm_debounce_timer.setInterval(100)
        # Instead of directly requesting completion, we dispatch calltip vs. completion here
        self._cm_debounce_timer.timeout.connect(self._cm_debounce_dispatch)

        # Poll timer to retrieve results from the worker
        self._cm_poll_timer = QTimer(self)
        self._cm_poll_timer.setInterval(50)  # 10 times/second
        self._cm_poll_timer.timeout.connect(self._cm_check_result)
        self._cm_poll_timer.start()

        # Single ongoing request flag, used for both completions and calltips
        self._cm_ongoing_request = False

        # Track the cursor position when a request was made
        self._cm_requested_cursor_pos = None
        self._cm_requested_calltip_cursor_pos = None

        # Create the popup for completions
        self._cm_completion_popup = CompletionPopup(self)

        # Create (but keep hidden) our persistent calltip widget
        self._cm_calltip_widget = CalltipWidget(self)
        self._cm_calltip_widget.hide()
        self._cm_paren_prefix = None
        logger.info("CompletionMixin initialized.")

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
        if self._cm_paren_prefix is None:
            self._update_paren_prefix_cache()
        pos = self.textCursor().position()
        # If the balance is > 0 at pos, there's at least one '(' not yet closed.
        return self._cm_paren_prefix[pos] > 0
    
    def _is_navigation_key(self, event):
        """Same as before, just returning True if event.key is an arrow/home/end etc."""
        nav_keys = {
            Qt.Key_Up, Qt.Key_Down, Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp,
            Qt.Key_PageDown
        }
        return event.key() in nav_keys
    
    def keyPressEvent(self, event):
        """
        Updated logic to remove duplication:
          1) We define a helper _cm_hide_and_recheck_calltip_if_unclosed() for the
             arrow-key cases where we cross '(' or ')'.
          2) We no longer update the paren prefix cache after navigation keys,
             per your request.
          3) The rest of the logic remains the same as before.
        """
        typed_char = event.text()
        old_pos = self.textCursor().position()  # remember cursor position before super()
    
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
            # Let the cursor move first.
            super().keyPressEvent(event)
            new_pos = self.textCursor().position()
    
            # If we moved left and jumped over '(' => hide & re-check
            if is_left and (old_pos - new_pos == 1):
                # The char at new_pos is the newly "revealed" character we jumped over
                text = self.toPlainText()
                if 0 <= new_pos < len(text) and text[new_pos] in '()':
                    self._cm_hide_and_recheck_calltip_if_unclosed()
                return
    
            # If we moved right and jumped over ')' => hide & re-check
            if is_right and (new_pos - old_pos == 1):
                text = self.toPlainText()
                # The char at old_pos was the newly "passed" character
                if 0 <= old_pos < len(text) and text[old_pos] in '()':
                    self._cm_hide_and_recheck_calltip_if_unclosed()
                return
    
            # If we got here, it was a left/right arrow but not crossing '(' or ')',
            # so do nothing special about calltips.
            return
    
        # 4) If user pressed a navigation key (Home, End, PgUp, etc.), hide calltip and then re-check position.
        if self._is_navigation_key(event):
            # Process the navigation so the cursor actually moves.
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
            self._cm_debounce_timer.start()
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
    
        # 7) Update the paren cache after text changed (but not after arrow nav)
        self._update_paren_prefix_cache()
    
        # 8) If user typed "(", we show or update the calltip
        if typed_char == '(':
            logger.info("User typed '(' => requesting calltip.")
            self._cm_request_calltip()
    
        # If we removed an "(", hide calltip
        if backspace_removing_open_paren:
            logger.info("User removed '(' => hiding calltip.")
            self._cm_hide_calltip()
    
        # 9) Hide or keep the completion popup based on typed char
        if typed_char:
            if typed_char.isalnum() or typed_char in ('_', '.') or event.key() == Qt.Key_Backspace:
                logger.info(f"User typed identifier-like char {typed_char!r}; keeping popup open (if visible).")
            else:
                logger.info(f"User typed non-identifier char {typed_char!r}; hiding popup.")
                self._cm_completion_popup.hide()
    
        # 10) Finally, launch the debounce => triggers either calltip or completions
        self._cm_debounce_timer.start()
    
    
    def _cm_hide_and_recheck_calltip_if_unclosed(self):
        """
        Helper to hide the calltip if currently visible, then re-request it if
        we still have an unmatched '(' at the cursor.
        """
        if self._cm_calltip_widget.isVisible():
            self._cm_hide_calltip()
        # We skip updating self._update_paren_prefix_cache() here because you noted
        # it's not necessary after navigation keys. If you do want to re-check the
        # text or cursor, feel free to add it back.
        if self._cursor_follows_unclosed_paren():
            self._cm_request_calltip()
    
    
    def _cm_debounce_dispatch(self):
        """
        Called by the debounce timer to decide whether we should request
        a calltip (if the last non-whitespace char is '(' or ',')
        or a normal completion otherwise.
        """
        code = self.toPlainText()
        trimmed = code.rstrip()
        if not trimmed:
            logger.info("No code typed, skipping request in _cm_debounce_dispatch.")
            return
        last_char = trimmed[-1]
    
        if last_char in ('(', ','):
            logger.info("Debounced => last char is %r => requesting calltip.", last_char)
            self._cm_request_calltip()
        else:
            logger.info("Debounced => requesting normal completion.")
            self._cm_request_completion(multiline=False)

    def _cm_request_completion(self, multiline=False):
        """Send a completion request if one is not already in progress."""
        if self._cm_ongoing_request:
            logger.info("Completion request attempted while one is ongoing; ignoring.")
            return

        code = self.toPlainText()
        cursor_pos = self.textCursor().position()
        logger.info("Requesting completions at cursor_pos=%d, multiline=%s", cursor_pos, multiline)

        self._cm_ongoing_request = True
        self._cm_requested_cursor_pos = cursor_pos
        self._cm_request_queue.put({
            'action': 'complete',
            'code': code,
            'cursor_pos': cursor_pos,
            'multiline': multiline,
            'path': self._cm_file_path,
            'language': self._cm_language
        })

    def _cm_request_calltip(self):
        """Send a calltip request."""
        if self._cm_ongoing_request:
            logger.info("Calltip request attempted while request is ongoing; ignoring.")
            return

        code = self.toPlainText()
        cursor_pos = self.textCursor().position()
        logger.info("Requesting calltip at cursor_pos=%d", cursor_pos)

        self._cm_ongoing_request = True
        self._cm_requested_calltip_cursor_pos = cursor_pos
        self._cm_request_queue.put({
            'action': 'calltip',
            'code': code,
            'cursor_pos': cursor_pos,
            'path': self._cm_file_path,
            'language': self._cm_language
        })

    def _cm_hide_calltip(self):
        """Hide the calltip widget."""
        logger.info("Hiding calltip widget.")
        self._cm_calltip_widget.hide()

    def _cm_check_result(self):
        """Check for completion or calltip results from the external worker."""
        try:
            result = self._cm_result_queue.get_nowait()
        except Empty:
            self._cm_poll_timer.start()
            return

        # If it's not a dict, ignore
        if not isinstance(result, dict):
            logger.info("Got invalid response (not a dict): %s", result)
            return

        action = result.get('action', None)
        if action is None:
            logger.info("Missing 'action' in worker response: %s", result)
            return
        self._cm_ongoing_request = False

        if action == 'complete':
            logger.info("Handling 'complete' action with result: %s", result)
            self._cm_complete(**result)
        elif action == 'calltip':
            logger.info("Handling 'calltip' action with result: %s", result)
            self._cm_calltip(**result)
        else:
            logger.info("Ignoring unknown action: %s", action)

    def _cm_complete(self, action, completions, cursor_pos, multiline):
        """Handle completion results from the worker."""
        # Discard if cursor changed since the request
        if cursor_pos != self.textCursor().position():
            logger.info(
                "Discarding completions because cursor changed (old=%d, new=%d).",
                cursor_pos, self.textCursor().position())
            return

        if not completions:
            logger.info("No completions returned.")
            self._cm_completion_popup.hide()
            return

        if multiline:
            logger.info("Inserting first multiline completion: '%s'", completions[0])
            completion_text = completions[0]
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
            self._cm_completion_popup.show_completions(completions)

    def _cm_calltip(self, action, signatures, cursor_pos):
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

        # Convert its bottom-left to global coordinates, then shift down
        global_pos = self.mapToGlobal(cr.bottomLeft())
        global_pos.setY(global_pos.y() + cr.height())

        self._cm_calltip_widget.move(global_pos)
        self._cm_calltip_widget.show()

    def closeEvent(self, event):
        """
        Ensure the worker shuts down. Then let the next class in the MRO
        handle the close event (which is typically QPlainTextEdit).
        """
        logger.info("Closing editor, shutting down completion worker.")
        self._cm_request_queue.put({'action': 'quit'})  # safer than put(None)
        self._cm_worker_process.join()
        super().closeEvent(event)
        logger.info("Editor closed, worker process joined.")
