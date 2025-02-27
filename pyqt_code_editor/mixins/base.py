from ..worker import manager
from qtpy.QtCore import QTimer, Signal
from qtpy.QtGui import QTextCursor
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

active_editor = None


class Base:
    
    code_editor_file_path = None
    code_editor_colors = None
    code_editor_language = 'text'
    modification_changed = Signal(object, bool)
    received_focus = Signal(object)
    
    def __init__(self, *args, **kwargs):
        # Optionally set the language. This is mainly for generic editors that
        # need to support multiple languages. This needs to be stripped from
        # the kwargs because it's not supported by QPlainTextEdit
        language = kwargs.pop('language', None)
        if language is not None:
            self.code_editor_language = language
        super().__init__(*args, **kwargs)
        logger.info("Initializing Base")
        self.installEventFilter(self)
        # Poll timer to retrieve results from the worker
        self._cm_result_queue = None
        self._cm_worker_pid = None
        self._cm_poll_timer = QTimer(self)
        self._cm_poll_timer.setInterval(50)  # 10 times/second
        self._cm_poll_timer.timeout.connect(self._cm_check_result)
        self._cm_poll_timer.start()
        self.code_editor_line_annotations = {}
        # Keep track of modified status
        self.modified = False
        self.modificationChanged.connect(self.set_modified)
        # Dictionary mapping pid -> result queue
        self._active_requests = {}        
        
    def eventFilter(self, obj, event):
        """Can be implement in other mixin classes to filter certain events,
        for example to avoid certain keypresses from being consumed.
        """
        return False

    def focusInEvent(self, event):
        """Allows managing widgets, such as the editor panel, to keep track of
        which editor is active
        """
        super().focusInEvent(event)
        self.received_focus.emit(self)
    
    def refresh(self):
        """Can be called to indicate that the interface needs to be refreshed,
        and implement in other mixin classes to handle the actual refresh 
        logic.
        """
        pass
        
    def send_worker_request(self, **data):
        """
        Send a request to the worker manager. 
        This returns a unique queue/pid pair each time, 
        so we can handle multiple concurrent requests.
        """
        result_queue, pid = manager.send_worker_request(**data)
        self._active_requests[pid] = result_queue
        logger.info(f"Sent request to worker {pid}, now tracking {len(self._active_requests)} active requests.")

    def handle_worker_result(self, action, result):
        """
        Subclasses can override this to do specialized handling 
        for the action & result from the worker process.
        """
        pass

    def _cm_check_result(self):
        """
        Called periodically (e.g. via a QTimer) to check each active
        worker's queue. If there's a result, handle it;
        if the worker died or the result queue is empty, keep polling.
        """
        to_remove = []
        for pid, queue in self._active_requests.items():
            # 1) Check if the worker is still alive
            if not manager.check_worker_alive(pid):
                logger.warning(f"Worker process {pid} no longer alive. Removing from active requests.")
                to_remove.append(pid)
                continue

            # 2) If queue is empty, nothing more to do right now
            if queue.empty():
                continue

            # 3) Retrieve the result, mark worker free
            result = queue.get()
            manager.mark_worker_as_free(pid)

            # 4) Validate result structure
            if not isinstance(result, dict):
                logger.info(f"Got invalid response (not a dict) from {pid}: {result}")
                to_remove.append(pid)
                continue

            # 5) Extract action and pass it to our handler
            action = result.pop('action', None)
            if action is None:
                logger.info(f"Missing 'action' in worker response: {result}")
                to_remove.append(pid)
                continue

            logger.info(f"Received worker result from {pid}: action={action}")
            self.handle_worker_result(action, result)

            # 6) We're done with this particular request
            to_remove.append(pid)

        # Cleanup: remove completed or dead requests
        for pid in to_remove:
            self._active_requests.pop(pid, None)
        
    def set_modified(self, modified):
        logger.info(f'modified: {modified}')
        self.document().setModified(modified)
        self.modified = modified
        self.modification_changed.emit(self, modified)
        
    def jump_to_line(self, line_number=0):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.Start)
        cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, line_number)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def update_theme(self):
        """Mixins can implement this to update the theme in response to font changes
        etc.
        """
        pass
